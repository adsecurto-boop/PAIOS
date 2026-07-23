"""The HTTP binding: stdlib http.server around the pure ApiRouter.

Deliberately SINGLE-THREADED (plain HTTPServer, not ThreadingHTTPServer):
the JSON store and the runtime kernel are not synchronized for concurrent
mutation, so serializing requests at the transport is a correctness
decision, not a simplification.

Shutdown: Ctrl+C (KeyboardInterrupt) leaves serve_forever cleanly, the
socket is closed, and the composed Application is stopped — the mission's
graceful shutdown.
"""

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import TextIO

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.api import ai_settings, assistant_support
from paios.api.config import ApiConfig
from paios.api.mobile_support import PairingService
from paios.api.errors import payload as error_payload
from paios.api.routes import ApiRouter
from paios.planning.metadata_planner import MetadataPlanner
from paios.planning.service import PlanningService
from paios.system.backup import BackupManager

_MAX_BODY_BYTES = 1_000_000


class _ApiRequestHandler(BaseHTTPRequestHandler):
    """Wire format only: bytes in, JSON out; routing lives in ApiRouter."""

    server_version = "PaiosApi/1.0"

    # The bound ApiServer injects the router via the HTTPServer instance.
    def _router(self) -> ApiRouter:
        return self.server.router  # type: ignore[attr-defined]

    def _respond(self, status: int, body: dict) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return None
        if length > _MAX_BODY_BYTES:
            return self._respond(
                413, error_payload(413, "ApiError", "Request body too large")
            )
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._respond(
                400, error_payload(400, "ApiError", "Body is not valid JSON")
            )
            raise _BadBody()

    def _context(self) -> dict:
        """Transport context for the router: auth headers (mobile
        bearer tokens) and the client address (loopback-only routes)."""
        return {
            "headers": dict(self.headers.items()),
            "client_host": self.client_address[0],
        }

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        status, body = self._router().handle(
            "GET", self.path, **self._context()
        )
        self._respond(status, body)

    def do_POST(self) -> None:  # noqa: N802
        try:
            body = self._read_body()
        except _BadBody:
            return
        status, response = self._router().handle(
            "POST", self.path, body, **self._context()
        )
        self._respond(status, response)

    def do_PUT(self) -> None:  # noqa: N802 (M20: edit/metadata routes)
        try:
            body = self._read_body()
        except _BadBody:
            return
        status, response = self._router().handle(
            "PUT", self.path, body, **self._context()
        )
        self._respond(status, response)

    def do_DELETE(self) -> None:  # noqa: N802 (M20: planning stores only)
        status, response = self._router().handle(
            "DELETE", self.path, **self._context()
        )
        self._respond(status, response)

    def log_message(self, format: str, *args) -> None:
        """No console noise; requests go to the structured log (M16).
        Without configured handlers this is a no-op, preserving the
        pre-M16 silence."""
        import logging

        logging.getLogger("paios.api").info(format, *args)


class _BadBody(Exception):
    pass


class ApiServer:
    """Owns the Application lifecycle and the listening socket."""

    def __init__(
        self,
        config: ApiConfig | None = None,
        application: Application | None = None,
    ) -> None:
        self._config = config if config is not None else ApiConfig()
        # M20 composition: planning stores exist before the Application
        # so the MetadataPlanner can ride the Scheduler's R3 seam.
        self._planning = PlanningService(self._config.data_dir)
        self._app = (
            application
            if application is not None
            else Application(
                ApplicationConfig(
                    data_dir=self._config.data_dir,
                    planner=MetadataPlanner(self._planning.metadata),
                )
            )
        )
        self._owns_application = application is None
        backup_dir = (
            self._config.backup_dir
            if self._config.backup_dir is not None
            else str(Path(self._config.data_dir).parent / "backups")
        )
        self._backups = BackupManager(self._config.data_dir, backup_dir)
        # Intelligence layer: env > persisted ai-settings.json > ApiConfig.
        stored = ai_settings.load(self._config.data_dir)
        provider_default = (
            stored.get("provider") or self._config.ai_provider
        )
        model_default = stored.get("model") or self._config.ai_model
        resolved = assistant_support.resolve_provider(provider_default)
        (
            self._assistant_provider,
            self._assistant,
            self._assistant_reason,
        ) = assistant_support.compose_assistant(
            provider_default,
            model_default,
            api_key=ai_settings.api_key_for(self._config.data_dir, resolved),
        )
        self._mobile = PairingService(self._config.data_dir)
        self._http: HTTPServer | None = None
        self._serving = False
        #: M22: mDNS advertiser, started only in Local Network mode so a
        #: phone can discover the desktop without a typed IP. None in
        #: loopback mode (nothing on 127.0.0.1 to discover).
        self._advertiser = None
        #: M23: the outbound relay connector (remote access), started when
        #: relay-settings.json is enabled and configured. None otherwise.
        self._relay_connector = None
        self._bound_port = None

    def assistant_summary(self) -> list[str]:
        """Human-readable startup lines: provider, reason, active mode."""
        if self._assistant is not None:
            return [
                f"AI provider: {self._assistant_provider} (available)",
            ]
        return [
            f"AI provider: {self._assistant_provider}",
            f"Reason: {self._assistant_reason}",
            "Running deterministic heuristic mode"
            " (planning still works, without a language model).",
        ]

    @property
    def application(self) -> Application:
        return self._app

    @property
    def port(self) -> int:
        """The actual bound port (resolves 0 to the OS-chosen port)."""
        if self._http is None:
            raise RuntimeError("Server is not started")
        return self._http.server_address[1]

    def start(self) -> None:
        """Start the Application and bind the socket (no serving yet).

        The bind host honours the persisted access mode (M21): a phone
        can only reach PAIOS after the user picks Local Network on the
        Networking page, which writes network-settings.json here."""
        if not self._app.started:
            self._app.start()
        import paios.system.network as network

        data_dir = Path(self._config.data_dir)
        bind_host = network.resolve_bind_host(data_dir, self._config.host)
        http = HTTPServer(
            (bind_host, self._config.port), _ApiRequestHandler
        )
        http.router = ApiRouter(  # type: ignore[attr-defined]
            self._app,
            planning=self._planning,
            backups=self._backups,
            assistant=self._assistant,
            assistant_provider=self._assistant_provider,
            assistant_reason=self._assistant_reason,
            mobile=self._mobile,
            ai_dir=data_dir,
            network_dir=data_dir,
            bound_host=bind_host,
            bound_port=self._http_port_hint(http),
            discovery=self._start_discovery(bind_host, http, network),
            relay_status=self._relay_status,
            relay_reload=self._reload_relay,
            relay_authorize=self._relay_authorize,
        )
        self._http = http
        self._bound_port = self._http_port_hint(http)
        self._start_relay()
        import logging

        for line in self.assistant_summary():
            logging.getLogger("paios.api").info(line)

    # --- remote access connector (M23) -----------------------------------

    def _start_relay(self) -> None:
        """Open the outbound tunnel when remote access is configured and
        enabled. Best-effort: a bad/absent config simply leaves remote
        access off (LAN and loopback are unaffected)."""
        from paios.api import relay_settings
        from paios.system.relay_client import RelayConnector

        data_dir = self._config.data_dir
        settings = relay_settings.config(data_dir)
        key = relay_settings.account_key_for(data_dir)
        if not settings["enabled"] or not settings["relay_url"] or not key:
            return
        connector = RelayConnector(
            settings["relay_url"],
            settings["account"],
            key,
            f"http://127.0.0.1:{self._bound_port}",
        )
        connector.start()
        self._relay_connector = connector

    def _reload_relay(self) -> None:
        """Apply changed relay settings without restarting the server."""
        if self._relay_connector is not None:
            self._relay_connector.stop()
            self._relay_connector = None
        self._start_relay()

    def _relay_status(self) -> dict:
        from paios.api import relay_settings

        status = relay_settings.config(self._config.data_dir)
        if self._relay_connector is not None:
            status.update(self._relay_connector.status())
        else:
            status.update({"connected": False, "last_error": None})
        return status

    def _relay_authorize(self, token_hash: str) -> bool:
        """Register a freshly paired phone with the relay so it can be
        reached remotely. No-op (False) when remote access is off."""
        if self._relay_connector is None:
            return False
        return self._relay_connector.authorize_device(token_hash)

    def _start_discovery(self, bind_host: str, http: HTTPServer, network):
        """Advertise the API over mDNS when it is LAN-reachable, so a
        phone finds it with no typed IP. Best-effort and loopback-safe:
        loopback mode advertises nothing (returns None)."""
        if bind_host != network.ANY_HOST:
            return None
        import paios.system.discovery as discovery

        info = discovery.ServiceInfo(
            port=self._http_port_hint(http),
            address=network.local_ip(),
            instance="PAIOS on " + network.hostname(),
            hostname=network.hostname().split(".")[0] or "paios",
            properties={"server": "paios", "path": "/mobile"},
        )
        advertiser = discovery.DiscoveryAdvertiser(info)
        advertiser.start()  # never raises; False on a busy mDNS port
        self._advertiser = advertiser
        return advertiser

    @staticmethod
    def _http_port_hint(http: HTTPServer) -> int:
        """The actually bound port (resolves an ephemeral 0 to the real
        one) so the Networking page shows the address phones must use."""
        return http.server_address[1]

    def serve_forever(self) -> None:
        if self._http is None:
            self.start()
        assert self._http is not None
        self._serving = True
        try:
            self._http.serve_forever()
        finally:
            self._serving = False

    def shutdown(self) -> None:
        """Stop serving, close the socket, stop the owned Application.

        HTTPServer.shutdown() blocks forever unless serve_forever is
        actually running (stdlib contract), so it is signalled only then;
        a bound-but-not-serving socket is simply closed."""
        if self._relay_connector is not None:
            self._relay_connector.stop()
            self._relay_connector = None
        if self._advertiser is not None:
            self._advertiser.stop()
            self._advertiser = None
        if self._http is not None:
            if self._serving:
                self._http.shutdown()
            self._http.server_close()
            self._http = None
        if self._owns_application and self._app.started:
            self._app.stop()


def serve(
    config: ApiConfig | None = None, output_stream: TextIO | None = None
) -> int:
    """Blocking development server with graceful Ctrl+C shutdown."""
    import sys

    out = output_stream if output_stream is not None else sys.stdout
    server = ApiServer(config)
    server.start()
    out.write(
        f"PAIOS API listening on http://{server._config.host}:{server.port}"
        "  (Ctrl+C to stop)\n"
    )
    for line in server.assistant_summary():
        out.write(line + "\n")
    out.flush()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        # serve_forever exited (Ctrl+C): close socket and application.
        if server._http is not None:
            server._http.server_close()
            server._http = None
        if server._app.started:
            server._app.stop()
        out.write("PAIOS API stopped.\n")
        out.flush()
    return 0
