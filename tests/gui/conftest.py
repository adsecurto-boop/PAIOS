"""GUI test fixtures: a live REST server + an offscreen Qt application.

The GUI tests exercise the real stack end to end: seeded store ->
Application -> ApiServer (ephemeral port, background thread) -> HTTP ->
ApiClient -> widgets. Qt renders offscreen (no display needed).

Only the FIXTURES import paios (to host the server the GUI talks to);
the GUI package itself imports nothing from paios — asserted by
test_forbidden_imports.
"""

import os
import threading

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from paios.api import ApiConfig, ApiServer
from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.repositories.factory import RepositoryFactory
from paios.runtime.clock import ManualClock

from paios_gui import ApiClient, GuiConfig
from paios_gui.main_window import MainWindow

from tests.application.conftest import T0, seed_rest_scenario


@pytest.fixture(scope="session")
def qapp():
    application = QApplication.instance() or QApplication([])
    yield application


@pytest.fixture
def live_server(tmp_path):
    """A real ApiServer over a seeded application, on an ephemeral port."""
    data_dir = tmp_path / "data"
    factory = RepositoryFactory(data_dir)
    factory.initialize()
    seed_rest_scenario(factory)
    application = Application(
        ApplicationConfig(data_dir=data_dir, clock=ManualClock(T0))
    )
    application.start()
    server = ApiServer(
        ApiConfig(port=0, data_dir=str(data_dir)), application=application
    )
    server.start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.port}"
    server.shutdown()
    thread.join(timeout=5)
    if application.started:
        application.stop()


@pytest.fixture
def client(live_server):
    return ApiClient(live_server, timeout=5.0)


@pytest.fixture
def window(qapp, client):
    gui_config = GuiConfig(base_url=client.base_url, refresh_seconds=60)
    main_window = MainWindow(client, gui_config)
    yield main_window
    main_window.close()
    main_window.deleteLater()


def unreachable_client() -> ApiClient:
    """A client pointed at a port nothing listens on."""
    return ApiClient("http://127.0.0.1:9", timeout=0.5)
