import json
import pytest
from pathlib import Path
from paios.api.server import ApiServer
from paios.api.config import ApiConfig
from paios.api.routes import ApiRouter

def test_first_install_cleans_operational_data(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Seed operational data files that should be deleted on first launch
    op_file = data_dir / "events.json"
    op_file.write_text("[{'event': 'old'}]", encoding="utf-8")
    
    # 2. Seed config files that should be PRESERVED
    conf_file = data_dir / "ai-settings.json"
    conf_file.write_text("{'provider': 'ollama'}", encoding="utf-8")
    
    # 3. Instantiate server (first run, sentinel does not exist yet)
    ApiServer(ApiConfig(data_dir=data_dir))
    
    # Sentinel should now exist
    assert (data_dir / "first_install_complete").exists()
    # Operational file should be cleared/reset to empty array
    assert op_file.read_text(encoding="utf-8") == "[]"
    # Config file should be preserved
    assert conf_file.read_text(encoding="utf-8") == "{'provider': 'ollama'}"

def test_assistant_providers_endpoint(api_app):
    from paios.assistant.adapters.null import NullAdapter
    from paios.assistant.provider_manager import ProviderManager
    from paios.assistant.orchestrator import AssistantOrchestrator
    manager = ProviderManager("null", {"null": NullAdapter()})
    orchestrator = AssistantOrchestrator(manager)
    # Compose active null router so we have composed providers
    router = ApiRouter(api_app, assistant=orchestrator, ai_dir=api_app._config.data_dir)
    status, payload = router.handle("GET", "/assistant/providers")
    assert status == 200
    assert "providers" in payload
    # At least "null" should be initialized.
    assert "null" in payload["providers"]
    assert "capabilities" in payload["providers"]["null"]
    assert payload["providers"]["null"]["capabilities"]["planning"] is True
