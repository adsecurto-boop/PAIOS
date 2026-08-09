"""Tests for PAIOS version and build reporting system."""

import io
import pytest
from paios import get_version_info, __build__
from paios.cli.main import main
from paios.api.routes import ApiRouter
from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios_gui.client import ApiClient


def test_get_version_info():
    info = get_version_info()
    assert isinstance(info, dict)
    assert info["version"] == "2.4.0"
    assert info["build"] == __build__
    assert "commit" in info
    assert isinstance(info["commit"], str)


def test_cli_version_command():
    sink = io.StringIO()
    code = main(["version"], output_stream=sink)
    assert code == 0
    output = sink.getvalue()
    assert "PAIOS version: 2.4.0" in output
    assert f"Build: {__build__}" in output
    assert "Git Commit:" in output


def test_api_version_endpoint(tmp_path):
    config = ApplicationConfig(data_dir=str(tmp_path / "data"))
    app = Application(config)
    router = ApiRouter(app)
    
    status, payload = router.handle("GET", "/system/version")
    assert status == 200
    assert payload["version"] == "2.4.0"
    assert payload["build"] == __build__
    assert "commit" in payload


def test_gui_client_get_version(monkeypatch):
    client = ApiClient("http://127.0.0.1:8765")
    
    # Mock the client's internal request method
    def mock_request(method, path, body=None, timeout=None):
        assert method == "GET"
        assert path == "/system/version"
        return {"version": "2.4.0", "build": "003", "commit": "abc1234"}
        
    monkeypatch.setattr(client, "_request", mock_request)
    info = client.get_version()
    assert info["version"] == "2.4.0"
    assert info["build"] == "003"
    assert info["commit"] == "abc1234"
