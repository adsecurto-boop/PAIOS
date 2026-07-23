"""Start / stop / restart the PAIOS API without a terminal (M21).

The GUI talks to the API over REST, but a dead server cannot be started
over HTTP — so the Networking page needs a local, non-REST way to run
one. This controller spawns the public ``paios serve`` command as a
child process; it imports nothing from the backend (the GUI's
REST-only discipline is preserved — a subprocess is not an import).

Everything is injectable, so the state machine is unit-tested with a
fake spawner and prober and no real server:

    spawner(command) -> process      (process has .poll()/.pid/.terminate())
    prober()         -> bool         (is something answering on the API?)

Under the product launcher (PAIOS.exe) the API is already supervised;
the controller detects that (the prober succeeds without an owned
child) and reports it as externally managed rather than starting a
second, conflicting server.
"""

import subprocess
import sys

from paios_gui.client import ApiClient


def _split_host_port(base_url: str) -> tuple[str, int]:
    """(host, port) from an http URL — plain string work so this module
    keeps HTTP (urllib) confined to client.py, the GUI's one doorway."""
    authority = base_url.split("//", 1)[-1].split("/", 1)[0]
    host, _, port = authority.partition(":")
    try:
        return host or "127.0.0.1", int(port) if port else 8765
    except ValueError:
        return host or "127.0.0.1", 8765


def default_serve_command(port: int | None = None) -> list[str]:
    """Run the API via the public CLI surface. ``paios`` on PATH when
    installed; the module entry point in a dev checkout — never an
    import of the backend into this process."""
    import shutil

    base = (
        [shutil.which("paios") or "paios", "serve"]
        if shutil.which("paios")
        else [sys.executable, "-m", "paios.cli", "serve"]
    )
    if port is not None:
        base.append(str(port))
    return base


def default_spawner(command: list[str]):
    creation_flags = 0
    if sys.platform == "win32":
        creation_flags = (
            subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
        )
    return subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creation_flags,
    )


class ServerController:
    def __init__(
        self,
        base_url: str,
        *,
        spawner=default_spawner,
        prober=None,
        command_builder=default_serve_command,
        probe_timeout: float = 1.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._host, self._port = _split_host_port(self._base_url)
        self._spawner = spawner
        self._prober = prober if prober is not None else self._http_probe
        self._command_builder = command_builder
        self._probe_client = ApiClient(self._base_url, timeout=probe_timeout)
        self._child = None  # a process we started and therefore own

    # --- probing ---------------------------------------------------------

    def _http_probe(self) -> bool:
        """True when the API answers GET /status — proof a server is up,
        whether we started it or the launcher did. HTTP stays in the
        client (the GUI's single doorway)."""
        try:
            self._probe_client.get_status()
            return True
        except Exception:
            return False

    def _child_alive(self) -> bool:
        return self._child is not None and self._child.poll() is None

    # --- status ----------------------------------------------------------

    def status(self) -> dict:
        reachable = self._prober()
        managed = self._child_alive()
        if reachable:
            state = "running"
        elif managed:
            state = "starting"  # spawned, not answering yet
        else:
            state = "stopped"
        return {
            "state": state,
            "reachable": reachable,
            "managed": managed,
            "external": reachable and not managed,
            "host": self._host,
            "port": self._port,
            "pid": self._child.pid if managed else None,
        }

    # --- lifecycle -------------------------------------------------------

    def start(self) -> dict:
        if self._prober():
            return {
                "started": False,
                "reason": "The PAIOS server is already running.",
            }
        if self._child_alive():
            return {
                "started": False,
                "reason": "A server is already starting.",
            }
        try:
            self._child = self._spawner(
                self._command_builder(self._port)
            )
        except OSError as error:
            self._child = None
            return {"started": False, "reason": str(error)}
        return {
            "started": True,
            "reason": "Starting the PAIOS server…",
            "pid": self._child.pid,
        }

    def stop(self) -> dict:
        if not self._child_alive():
            if self._prober():
                return {
                    "stopped": False,
                    "reason": "This server is managed by PAIOS itself and"
                    " cannot be stopped from here. Quit PAIOS to stop it.",
                }
            return {"stopped": False, "reason": "The server is not running."}
        child = self._child
        child.terminate()
        try:
            child.wait(timeout=8)
        except Exception:
            child.kill()
        self._child = None
        return {"stopped": True, "reason": "The PAIOS server was stopped."}

    def restart(self) -> dict:
        if self._child_alive():
            self.stop()
            return self.start()
        if self._prober():
            return {
                "started": False,
                "reason": "This server is managed by PAIOS; restart PAIOS"
                " to apply changes.",
            }
        return self.start()
