"""The server lifecycle controller (M21): start/stop/restart driven
through injected fakes — no real server, no real subprocess."""

from paios_gui.server_control import ServerController, _split_host_port


class FakeProc:
    def __init__(self, pid: int = 4321) -> None:
        self.pid = pid
        self._returncode = None
        self.terminated = False
        self.killed = False

    def poll(self):
        return self._returncode

    def terminate(self):
        self.terminated = True
        self._returncode = 0

    def kill(self):
        self.killed = True
        self._returncode = -9

    def wait(self, timeout=None):
        return self._returncode


def controller(reachable_values, spawner=None):
    """A controller whose prober returns successive values (or a
    constant) and whose spawner is a recording fake."""
    states = (
        list(reachable_values)
        if isinstance(reachable_values, (list, tuple))
        else None
    )

    def prober():
        if states is None:
            return reachable_values
        return states.pop(0) if states else False

    spawned = []

    def default_spawn(command):
        spawned.append(command)
        return FakeProc()

    control = ServerController(
        "http://127.0.0.1:8765",
        spawner=spawner or default_spawn,
        prober=prober,
    )
    control.spawned = spawned
    return control


class TestUrlSplit:
    def test_split_host_port(self):
        assert _split_host_port("http://192.168.1.5:9000") == (
            "192.168.1.5", 9000
        )
        assert _split_host_port("http://127.0.0.1:8765/") == (
            "127.0.0.1", 8765
        )
        assert _split_host_port("http://host") == ("host", 8765)


class TestStart:
    def test_start_spawns_when_down(self):
        control = controller(False)
        result = control.start()
        assert result["started"] is True
        assert control.spawned  # a serve command was launched
        assert control.status()["managed"] is True

    def test_start_refuses_when_already_running(self):
        control = controller(True)
        result = control.start()
        assert result["started"] is False
        assert "already running" in result["reason"].lower()
        assert not control.spawned

    def test_start_reports_spawn_failure(self):
        def boom(command):
            raise OSError("cannot exec")

        control = controller(False, spawner=boom)
        result = control.start()
        assert result["started"] is False
        assert "cannot exec" in result["reason"]


class TestStatus:
    def test_external_server_is_flagged(self):
        control = controller(True)
        state = control.status()
        assert state["reachable"] is True
        assert state["managed"] is False
        assert state["external"] is True
        assert state["state"] == "running"

    def test_stopped_when_nothing_answers(self):
        assert controller(False).status()["state"] == "stopped"


class TestStopRestart:
    def test_stop_terminates_owned_child(self):
        # Down (start spawns) then the probe still says down, but we own
        # a live child -> stop terminates it.
        control = controller([False, False, False])
        control.start()
        result = control.stop()
        assert result["stopped"] is True

    def test_cannot_stop_external_server(self):
        control = controller(True)
        result = control.stop()
        assert result["stopped"] is False
        assert "managed by paios" in result["reason"].lower()

    def test_restart_external_server_explains(self):
        control = controller(True)
        result = control.restart()
        assert result["started"] is False
        assert "restart paios" in result["reason"].lower()
