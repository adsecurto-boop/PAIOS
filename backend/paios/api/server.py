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
from paios.api import assistant_support
from paios.api.config import ApiConfig
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

    def do_GET(self) -> None:  # noqa: N802 (stdlib naming)
        status, body = self._router().handle("GET", self.path)
        self._respond(status, body)

    def do_POST(self) -> None:  # noqa: N802
        try:
            body = self._read_body()
        except _BadBody:
            return
        status, response = self._router().handle("POST", self.path, body)
        self._respond(status, response)

    def do_PUT(self) -> None:  # noqa: N802 (M20: edit/metadata routes)
        try:
            body = self._read_body()
        except _BadBody:
            return
        status, response = self._router().handle("PUT", self.path, body)
        self._respond(status, response)

    def do_DELETE(self) -> None:  # noqa: N802 (M20: planning stores only)
        status, response = self._router().handle("DELETE", self.path)
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
        self._assistant_provider = assistant_support.resolve_provider(
            self._config.ai_provider
        )
        self._assistant = assistant_support.build_orchestrator(
            self._assistant_provider, self._config.ai_model
        )
        self._http: HTTPServer | None = None
        self._serving = False

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
        """Start the Application and bind the socket (no serving yet)."""
        if not self._app.started:
            self._app.start()
        http = HTTPServer(
            (self._config.host, self._config.port), _ApiRequestHandler
        )
        http.router = ApiRouter(  # type: ignore[attr-defined]
            self._app,
            planning=self._planning,
            backups=self._backups,
            assistant=self._assistant,
            assistant_provider=self._assistant_provider,
        )
        self._http = http

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
