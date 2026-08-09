"""Regression tests for Gemini/Ollama provider selection and fallback diagnostics."""

import json
import urllib.error
import pytest
from paios.api.routes import ApiRouter
from paios.api.assistant_support import compose_assistant
from paios.api import ai_settings
from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.planning.service import PlanningService
from paios.system.backup import BackupManager
from paios.assistant.adapters import AdapterError


def test_gemini_diagnostics_flow(tmp_path, monkeypatch):
    # Set up DPAPI mocks
    monkeypatch.setattr("paios.api.ai_settings.protect_key", lambda x: "dpapi:" + x)
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key",
        lambda x: x.replace("dpapi:", "") if x.startswith("dpapi:") else None,
    )
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Track how many times each transport is called
    calls = {"gemini": 0, "ollama": 0}
    state = {
        "gemini_should_succeed": False,
        "ollama_should_fail": False
    }

    def mock_gemini_transport(url, payload, headers, timeout):
        calls["gemini"] += 1
        if state["gemini_should_succeed"]:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": '{"answer": "Gemini Success!", "bullets": [], "confidence": 1.0}'}
                            ]
                        }
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 20
                }
            }
        else:
            raise urllib.error.HTTPError(
                url, 401, "Unauthorized", headers, None
            )

    def mock_ollama_transport(url, payload, timeout):
        calls["ollama"] += 1
        if state["ollama_should_fail"]:
            raise Exception("Ollama server connection refused")
        if "chat" in url:
            return {"message": {"content": "{\"answer\": \"Ollama answer\", \"bullets\": [], \"confidence\": 1.0}"}}
        return {"version": "0.1.0"}

    # Apply mocks to the transport modules
    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport", mock_gemini_transport
    )
    monkeypatch.setattr(
        "paios.assistant.adapters.ollama.default_transport", mock_ollama_transport
    )

    # Instantiate Application
    app = Application(ApplicationConfig(data_dir=str(tmp_path / "app-data")))
    app.start()
    
    router = ApiRouter(
        app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=None,
        assistant_provider="none",
        ai_dir=ai_dir,
    )

    # Step 1: Gemini selected + valid-looking configuration => active provider remains Gemini after Apply/recomposition
    put_status, put_payload = router.handle(
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "AIzaFakeKey"
        }
    )
    assert put_status == 200
    assert put_payload["provider"] == "gemini"
    assert put_payload["available"] is True

    # Step 6: Persisted settings remain Gemini
    stored = ai_settings.load(ai_dir)
    assert stored.get("provider") == "gemini"
    assert stored.get("model") == "gemini-2.5-flash"
    assert ai_settings.has_stored_key(ai_dir, "gemini") is True

    # Check composition directly
    prov, orchestrator, reason = compose_assistant(
        "gemini", "gemini-2.5-flash", api_key="AIzaFakeKey", data_dir=ai_dir
    )
    assert prov == "gemini"
    assert orchestrator is not None
    assert orchestrator._adapter.get_active_provider() is not None
    assert orchestrator._adapter.get_active_provider().name == "gemini:gemini-2.5-flash"

    # Step 2: Gemini Test Connection invokes Gemini, not Ollama
    # Step 3: Gemini failure exposes the Gemini exception instead of silently returning Ollama/deterministic output
    # Step 4: Ollama is never called during Gemini Test Connection
    calls["gemini"] = 0
    calls["ollama"] = 0
    
    test_status, test_payload = router.handle("POST", "/assistant/test", {})
    assert test_status == 200
    assert test_payload["ok"] is False
    assert test_payload["source"] == "llm"
    assert "invalid api key" in test_payload["answer"].lower()
    
    assert calls["gemini"] == 1
    assert calls["ollama"] == 0

    # Step 5: Stopping Ollama does not cause the Gemini request to silently become deterministic
    # We will simulate "Ollama stopped" by making Ollama transport raise an error,
    # and we will mock Gemini to succeed so it doesn't fail.
    calls["gemini"] = 0
    calls["ollama"] = 0
    state["gemini_should_succeed"] = True
    state["ollama_should_fail"] = True

    # Since mobile assistant query uses check_device/require_device, let's mock it
    # To mock self._require_device(), we can monkeypatch router._require_device or set _mobile
    class FakeMobile:
        def authenticate(self, token, time):
            return "device_001"
    router._mobile = FakeMobile()

    query_status, query_payload = router.handle(
        "POST",
        "/mobile/assistant/query",
        {"text": "Is PAIOS active?"},
        client_host="127.0.0.1",
        headers={"authorization": "Bearer dev_key"}
    )
    print(f"DEBUG MOBILE QUERY: status={query_status}, payload={query_payload}")
    assert query_status == 200
    assert query_payload["source"] == "llm"
    assert query_payload["answer"] == "Gemini Success!"
    assert calls["gemini"] == 1
    assert calls["ollama"] == 0


def test_key_lookup_ignores_env_provider_override(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paios.assistant.adapters.ollama.default_transport",
        lambda url, payload, timeout: {"version": "0.1.0"},
    )
    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport",
        lambda url, payload, headers, timeout: {},
    )
    monkeypatch.setattr("paios.api.ai_settings.protect_key", lambda x: "dpapi:" + x)
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key",
        lambda x: x.replace("dpapi:", "") if x.startswith("dpapi:") else None,
    )
    monkeypatch.setenv("PAIOS_AI_PROVIDER", "ollama")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)
    ai_settings.store_api_key(ai_dir, "gemini", "secret-gemini-key")

    # Recompose assistant with active provider gemini but env override set to ollama.
    # The active provider resolves to ollama, but gemini should still compose and load its key.
    prov, orchestrator, reason = compose_assistant(
        "gemini", "gemini-2.5-flash", data_dir=ai_dir
    )
    assert orchestrator is not None
    gemini_adapter = orchestrator._adapter._providers.get("gemini")
    assert gemini_adapter is not None
    assert gemini_adapter._api_key == "secret-gemini-key"


def test_provider_model_precedence_and_consistency(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paios.assistant.adapters.ollama.default_transport",
        lambda url, payload, timeout: {"version": "0.1.0"},
    )
    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport",
        lambda url, payload, headers, timeout: {},
    )
    import sys
    from paios.api.assistant_support import resolve_model, resolve_provider, compose_assistant
    
    # 1. Test resolve_model consistency corrections
    # C. Ollama provider + Gemini model -> corrected safely to qwen2.5:7b
    assert resolve_model("ollama", "gemini-2.5-flash") == "qwen2.5:7b"
    assert resolve_model("ollama", "gemini-1.5-pro") == "qwen2.5:7b"
    
    # D. Gemini provider + Ollama model -> corrected safely to gemini-2.5-flash
    assert resolve_model("gemini", "qwen2.5:7b") == "gemini-2.5-flash"
    
    # Check other providers
    assert resolve_model("openai", "qwen2.5:7b") == "gpt-4o"
    assert resolve_model("anthropic", "qwen2.5:7b") == "claude-opus-4-8"
    
    # Safe defaults
    assert resolve_model("gemini", None) == "gemini-2.5-flash"
    assert resolve_model("ollama", None) == "qwen2.5:7b"

    # 2. Test resolve_provider environment overrides & frozen behavior
    monkeypatch.setenv("PAIOS_AI_PROVIDER", "ollama")
    
    # Non-frozen development behavior: PAIOS_AI_PROVIDER acts as override
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert resolve_provider("gemini") == "ollama"
    
    # Frozen desktop application behavior: stale PAIOS_AI_PROVIDER is IGNORED
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert resolve_provider("gemini") == "gemini"
    
    # Explicit PAIOS_ALLOW_ENV_OVERRIDE enables environment overrides when frozen
    monkeypatch.setenv("PAIOS_ALLOW_ENV_OVERRIDE", "1")
    assert resolve_provider("gemini") == "ollama"
    
    # Clean up allow override env
    monkeypatch.delenv("PAIOS_ALLOW_ENV_OVERRIDE", raising=False)
    
    # Explicit runtime/API selection (is_explicit=True) always bypasses environment override
    assert resolve_provider("gemini", is_explicit=True) == "gemini"

    # 3. Test compose_assistant startup vs explicit updates
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("PAIOS_AI_PROVIDER", "ollama")
    
    # Setup mock keys and data dir
    monkeypatch.setattr("paios.api.ai_settings.protect_key", lambda x: "dpapi:" + x)
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key",
        lambda x: x.replace("dpapi:", "") if x.startswith("dpapi:") else None,
    )
    
    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)
    ai_settings.store_api_key(ai_dir, "gemini", "my-gemini-key")
    
    # Case A: Stored Gemini provider + Gemini model + stored key -> Gemini is selected and composed when frozen
    prov, orchestrator, reason = compose_assistant(
        "gemini", "gemini-2.5-flash", data_dir=ai_dir, is_explicit=False
    )
    assert prov == "gemini"
    assert orchestrator is not None
    assert orchestrator._adapter.get_active_provider().name == "gemini:gemini-2.5-flash"
    
    # Case B: Stored Ollama provider + qwen2.5:7b -> Ollama is selected
    prov, orchestrator, reason = compose_assistant(
        "ollama", "qwen2.5:7b", data_dir=ai_dir, is_explicit=False
    )
    assert prov == "ollama"
    assert orchestrator is not None
    assert orchestrator._adapter.get_active_provider().name == "ollama:qwen2.5:7b"


def test_end_to_end_restart_restore_with_env_override(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paios.assistant.adapters.ollama.default_transport",
        lambda url, payload, timeout: {"version": "0.1.0"},
    )
    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport",
        lambda url, payload, headers, timeout: {},
    )
    import sys
    from paios.api.assistant_support import compose_assistant
    from paios.api import ai_settings

    # Mock DPAPI key protection
    monkeypatch.setattr("paios.api.ai_settings.protect_key", lambda x: "dpapi:" + x)
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key",
        lambda x: x.replace("dpapi:", "") if x.startswith("dpapi:") else None,
    )

    # 1. Setup stale environment variable (should be ignored in frozen mode)
    monkeypatch.setenv("PAIOS_AI_PROVIDER", "ollama")
    monkeypatch.setattr(sys, "frozen", True, raising=False)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Save a configuration with Gemini and a mismatched model name (should be corrected to gemini-2.5-flash)
    ai_settings.store_api_key(ai_dir, "gemini", "my-secret-key-123")

    # Verify that resolve_model corrects any mismatch
    from paios.api.assistant_support import resolve_model
    model = resolve_model("gemini", "qwen2.5:7b")
    assert model == "gemini-2.5-flash"

    ai_settings.save(ai_dir, {"provider": "gemini", "model": model})

    # 2. Simulate server restart: load configuration on startup
    stored = ai_settings.load(ai_dir)
    assert stored.get("provider") == "gemini"
    assert stored.get("model") == "gemini-2.5-flash"

    provider_default = stored.get("provider") or "none"
    model_default = stored.get("model")

    # 3. Resolve active provider and compose assistant
    from paios.api.assistant_support import resolve_provider
    resolved_prov = resolve_provider(provider_default, is_explicit=False)

    # Assert that because sys.frozen = True and PAIOS_ALLOW_ENV_OVERRIDE is not set,
    # the resolved provider is "gemini" (the stale environment variable is ignored!)
    assert resolved_prov == "gemini"

    # Compose the assistant using the stored key
    stored_key = ai_settings.api_key_for(ai_dir, resolved_prov)
    assert stored_key == "my-secret-key-123"

    prov, orchestrator, reason = compose_assistant(
        provider_default, model_default, api_key=stored_key, data_dir=ai_dir, is_explicit=False
    )

    # Assert the composed assistant is Gemini and has the correct model and key
    assert prov == "gemini"
    assert orchestrator is not None
    gemini_adapter = orchestrator._adapter._providers.get("gemini")
    assert gemini_adapter is not None
    assert gemini_adapter._model == "gemini-2.5-flash"
    assert gemini_adapter._api_key == "my-secret-key-123"



