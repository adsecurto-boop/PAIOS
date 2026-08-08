"""The intelligence layer and the mobile companion API. Covers:
AI settings persistence + live recomposition, hardware-driven model recommendation,
the daily-rhythm workflows in BOTH paths (LLM via the null adapter, deterministic without one),
and the /mobile namespace (pairing, token auth, loopback-only administration, offline-queue idempotency).
No network anywhere.
"""

import subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest

from paios.api import ai_settings, assistant_support, ollama_support
from paios.api.mobile_support import PairingService
from paios.api.routes import ApiRouter
from paios.assistant.adapters.null import NullAdapter
from paios.assistant.orchestrator import AssistantOrchestrator
from paios.planning.service import PlanningService
from paios.system import hardware
from paios.system.backup import BackupManager


def build_router(api_app, tmp_path, with_assistant=False):
    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)
    return ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=(
            AssistantOrchestrator(NullAdapter()) if with_assistant else None
        ),
        assistant_provider="null" if with_assistant else "none",
        mobile=PairingService(ai_dir),
        ai_dir=ai_dir,
    )


@pytest.fixture
def offline_router(api_app, tmp_path):
    """No AI provider — the deterministic path must answer everything."""
    return build_router(api_app, tmp_path, with_assistant=False)


@pytest.fixture
def ai_router(api_app, tmp_path):
    """The null adapter: the full LLM pipeline with zero network."""
    return build_router(api_app, tmp_path, with_assistant=True)


def ok(router, method, path, body=None, expect=200, **context):
    status, payload = router.handle(method, path, body, **context)
    assert status == expect, payload
    return payload


# --- hardware + model recommendation ----------------------------------------

class TestModelRecommendation:
    def test_8gb_machine_gets_small_models(self):
        choices = hardware.recommend_models(8.0)
        names = [choice.name for choice in choices]
        assert "qwen2.5:3b" in names
        assert "qwen2.5:7b" not in names
        recommended = [c for c in choices if c.recommended]
        assert [c.name for c in recommended] == ["qwen2.5:3b"]

    def test_16gb_machine_recommends_qwen_7b(self):
        choices = hardware.recommend_models(16.0)
        names = [choice.name for choice in choices]
        assert {"qwen2.5:7b", "llama3.1:8b", "mistral:7b"} <= set(names)
        assert "qwen2.5:14b" not in names
        assert [c.name for c in choices if c.recommended] == ["qwen2.5:7b"]

    def test_32gb_machine_allows_larger_models(self):
        choices = hardware.recommend_models(32.0)
        names = [choice.name for choice in choices]
        assert "qwen2.5:14b" in names
        assert [c.name for c in choices if c.recommended] == ["qwen2.5:14b"]

    def test_tiny_machine_still_gets_an_offer(self):
        choices = hardware.recommend_models(2.0)
        assert len(choices) == 1
        assert choices[0].recommended

    def test_exactly_one_recommendation_always(self):
        for ram in (4, 8, 12, 16, 24, 32, 64):
            recommended = [
                c for c in hardware.recommend_models(float(ram)) if c.recommended
            ]
            assert len(recommended) == 1, f"ram={ram}"

    def test_detect_never_raises(self):
        profile = hardware.detect()
        assert profile.cpu_cores >= 1
        assert profile.ram_gb >= 0.0

    def test_gpu_detection_is_cached_until_forced_refresh(self):
        calls = []

        def fake_runner(*args, **kwargs):
            calls.append((args, kwargs))
            return SimpleNamespace(
                returncode=0,
                stdout="NVIDIA RTX 4090,24576\n",
                stderr="",
            )

        hardware._reset_gpu_cache()
        first = hardware.detect_gpu(runner=fake_runner)
        second = hardware.detect_gpu(runner=fake_runner)
        third = hardware.detect_gpu(runner=fake_runner, force_refresh=True)

        assert first == ("NVIDIA RTX 4090", 24.0)
        assert second == first
        assert third == first
        assert len(calls) == 2

    @pytest.mark.skipif(
        subprocess.os.name != "nt",
        reason="Windows-only subprocess hiding behavior",
    )
    def test_windows_gpu_probe_uses_hidden_subprocess_flags(self):
        seen = {}

        def fake_runner(*args, **kwargs):
            seen.update(kwargs)
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        hardware._reset_gpu_cache()
        hardware.detect_gpu(runner=fake_runner, force_refresh=True)
        assert seen["creationflags"] & subprocess.CREATE_NO_WINDOW
        assert seen["startupinfo"].wShowWindow == subprocess.SW_HIDE


# --- AI settings + config endpoint ------------------------------------------

class TestAiSettings:
    def test_save_and_load_roundtrip(self, tmp_path):
        ai_settings.save(tmp_path, {"provider": "ollama", "model": "x"})
        assert ai_settings.load(tmp_path)["provider"] == "ollama"

    @pytest.mark.skipif(
        not hasattr(__import__("ctypes"), "windll"),
        reason="DPAPI is Windows-only",
    )
    def test_api_key_is_stored_protected_and_decrypts(self, tmp_path):
        assert ai_settings.store_api_key(tmp_path, "openai", "sk-secret")
        raw = ai_settings.settings_path(tmp_path).read_text(
            encoding="utf-8"
        )
        assert "sk-secret" not in raw  # never plain on disk
        assert ai_settings.api_key_for(tmp_path, "openai") == "sk-secret"

    def test_put_config_switches_provider_live(
        self, offline_router, monkeypatch
    ):
        monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
        before = ok(offline_router, "GET", "/assistant/status")
        assert before["available"] is False

        after = ok(
            offline_router,
            "PUT",
            "/assistant/config",
            {"provider": "null"},
        )
        assert after["available"] is True
        assert after["provider"] == "null"

        # And the plain status endpoint agrees without a restart.
        assert ok(offline_router, "GET", "/assistant/status")[
            "available"
        ] is True

    def test_put_config_rejects_unknown_provider(self, offline_router):
        status, _ = offline_router.handle(
            "PUT", "/assistant/config", {"provider": "skynet"}
        )
        assert status == 400

    def test_get_config_lists_providers(self, offline_router, monkeypatch):
        monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
        payload = ok(offline_router, "GET", "/assistant/config")
        assert "ollama" in payload["providers"]
        assert payload["env_override"] is False

    def test_assistant_test_answers_in_both_modes(
        self, offline_router, ai_router
    ):
        offline = ok(offline_router, "POST", "/assistant/test", {})
        assert offline["source"] == "heuristic" and offline["ok"] is True

        online = ok(ai_router, "POST", "/assistant/test", {})
        assert online["source"] == "llm" and online["ok"] is True
        assert online["adapter"] == "null"


# --- daily-rhythm workflows ---------------------------------------------------

class TestDailyRhythm:
    def test_morning_plan_heuristic_shape(self, offline_router):
        payload = ok(
            offline_router,
            "POST",
            "/assistant/morning-plan",
            {"sleep_hours": 5, "energy": "low"},
        )
        assert payload["source"] == "heuristic"
        assert isinstance(payload["timeline"], list)
        assert isinstance(payload["priorities"], list)
        assert any("sleep" in risk for risk in payload["risks"])

    def test_morning_plan_llm_path_keeps_deterministic_facts(
        self, ai_router
    ):
        payload = ok(
            ai_router,
            "POST",
            "/assistant/morning-plan",
            {"mood": "good"},
        )
        assert payload["source"] == "llm"
        assert payload["adapter"] == "null"
        assert "timeline" in payload and "risks" in payload

    def test_evening_review_heuristic_counts_today(self, offline_router):
        payload = ok(
            offline_router,
            "POST",
            "/assistant/evening-review",
            {"notes": "long day"},
        )
        assert payload["source"] == "heuristic"
        assert "completed" in payload
        assert "long day" in payload["answer"]

    def test_weekly_review_heuristic_has_seven_days(self, offline_router):
        payload = ok(offline_router, "POST", "/assistant/weekly-review", {})
        assert payload["source"] == "heuristic"
        assert len(payload["per_day"]) == 7

    def test_weekly_review_llm_path(self, ai_router):
        payload = ok(ai_router, "POST", "/assistant/weekly-review", {})
        assert payload["source"] == "llm"
        assert len(payload["per_day"]) == 7


# --- mobile pairing + auth ----------------------------------------------------

def pair_device(router, name="Pixel Test") -> str:
    started = ok(router, "POST", "/mobile/pairing/start")
    paired = ok(
        router,
        "POST",
        "/mobile/pair",
        {"code": started["code"], "device_name": name},
        expect=201,
    )
    return paired["token"]


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestMobilePairing:
    def test_full_pairing_flow_issues_a_working_token(self, offline_router):
        token = pair_device(offline_router)
        payload = ok(
            offline_router,
            "GET",
            "/mobile/timeline",
            headers=bearer(token),
        )
        assert "entries" in payload and "server_time" in payload

    def test_wrong_code_is_rejected(self, offline_router):
        ok(offline_router, "POST", "/mobile/pairing/start")
        status, _ = offline_router.handle(
            "POST",
            "/mobile/pair",
            {"code": "000000", "device_name": "x"},
        )
        assert status == 401

    def test_code_is_single_use(self, offline_router):
        started = ok(offline_router, "POST", "/mobile/pairing/start")
        ok(
            offline_router,
            "POST",
            "/mobile/pair",
            {"code": started["code"]},
            expect=201,
        )
        status, _ = offline_router.handle(
            "POST",
            "/mobile/pair",
            {"code": started["code"]},
        )
        assert status == 401

    def test_unpaired_requests_are_401(self, offline_router):
        for path in (
            "/mobile/timeline",
            "/mobile/tasks",
            "/mobile/logs",
            "/mobile/study",
        ):
            status, _ = offline_router.handle("GET", path)
            assert status == 401, path

    def test_pairing_admin_is_loopback_only(self, offline_router):
        status, _ = offline_router.handle(
            "POST",
            "/mobile/pairing/start",
            None,
            client_host="192.168.1.50",
        )
        assert status == 403

        # The phone-facing half is NOT loopback-restricted.
        started = ok(offline_router, "POST", "/mobile/pairing/start")
        ok(
            offline_router,
            "POST",
            "/mobile/pair",
            {"code": started["code"]},
            expect=201,
            client_host="192.168.1.50",
        )

    def test_tokens_are_stored_hashed(self, offline_router, tmp_path):
        token = pair_device(offline_router)
        stored = next(
            (tmp_path / "ai-data").glob("mobile-devices.json")
        ).read_text(encoding="utf-8")
        assert token not in stored

    def test_revoked_device_loses_access(self, offline_router):
        token = pair_device(offline_router)
        devices = ok(offline_router, "GET", "/mobile/pairing/devices")
        device_id = devices["devices"][0]["device_id"]
        ok(
            offline_router,
            "DELETE",
            f"/mobile/pairing/devices/{device_id}",
        )
        status, _ = offline_router.handle(
            "GET",
            "/mobile/timeline",
            None,
            headers=bearer(token),
        )
        assert status == 401

    def test_auth_endpoint_validates_tokens(self, offline_router):
        token = pair_device(offline_router)
        payload = ok(
            offline_router,
            "POST",
            "/mobile/auth",
            {"token": token},
        )
        assert payload["valid"] is True

        status, _ = offline_router.handle(
            "POST",
            "/mobile/auth",
            {"token": "bogus"},
        )
        assert status == 401


class TestMobileData:
    def test_tasks_roundtrip(self, offline_router):
        token = pair_device(offline_router)
        created = ok(
            offline_router,
            "POST",
            "/mobile/tasks",
            {"title": "From the phone"},
            expect=201,
            headers=bearer(token),
        )
        assert created["materialized"] in (True, False)

        events = ok(
            offline_router,
            "GET",
            "/mobile/tasks",
            headers=bearer(token),
        )
        titles = [event["description"] for event in events["events"]]
        assert "From the phone" in titles

    def test_log_sync_is_idempotent_by_client_id(self, offline_router):
        token = pair_device(offline_router)
        entry = {
            "kind": "journal",
            "text": "offline note",
            "client_id": "phone-abc-1",
        }
        first = ok(
            offline_router,
            "POST",
            "/mobile/logs",
            entry,
            expect=201,
            headers=bearer(token),
        )
        second = ok(
            offline_router,
            "POST",
            "/mobile/logs",
            entry,
            expect=201,
            headers=bearer(token),
        )
        assert first["id"] == second["id"]  # duplicate suppressed

        entries = ok(
            offline_router,
            "GET",
            "/mobile/logs",
            headers=bearer(token),
        )["entries"]
        assert len(
            [e for e in entries if e["client_id"] == "phone-abc-1"]
        ) == 1

    def test_logs_filter_by_day_segment(self, offline_router):
        token = pair_device(offline_router)
        record = ok(
            offline_router,
            "POST",
            "/mobile/logs",
            {"kind": "mood", "text": "good"},
            expect=201,
            headers=bearer(token),
        )
        day = record["day"]
        payload = ok(
            offline_router,
            "GET",
            f"/mobile/logs/{day}",
            headers=bearer(token),
        )
        assert all(entry["day"] == day for entry in payload["entries"])
        assert payload["entries"]

    def test_study_endpoint_serves_knowledge_and_logs(self, offline_router):
        token = pair_device(offline_router)
        ok(
            offline_router,
            "POST",
            "/mobile/logs",
            {"kind": "study", "text": "reviewed DDD chapter 4"},
            expect=201,
            headers=bearer(token),
        )
        payload = ok(
            offline_router,
            "GET",
            "/mobile/study",
            headers=bearer(token),
        )
        assert "knowledge" in payload
        assert payload["study_logs"][0]["text"].startswith("reviewed")

    def test_assistant_query_falls_back_without_ai(self, offline_router):
        token = pair_device(offline_router)
        payload = ok(
            offline_router,
            "POST",
            "/mobile/assistant/query",
            {"text": "how is my week?"},
            headers=bearer(token),
        )
        assert payload["source"] == "heuristic"

    def test_assistant_query_uses_llm_when_available(self, ai_router):
        token = pair_device(ai_router)
        payload = ok(
            ai_router,
            "POST",
            "/mobile/assistant/query",
            {"text": "how is my week?"},
            headers=bearer(token),
        )
        assert payload["source"] == "llm"
        assert payload["adapter"] == "null"


# --- ollama management (no server, injectable everything) ---------------------

class TestOllamaSupport:
    def test_status_reports_not_running_gracefully(self):
        def dead_fetcher(url, timeout):
            raise OSError("connection refused")

        payload = ollama_support.status(fetcher=dead_fetcher)
        assert payload["server_running"] is False
        assert payload["install_hint"]

    def test_status_lists_models_when_running(self):
        def live_fetcher(url, timeout):
            return {
                "models": [
                    {"name": "qwen2.5:7b", "size": 4_700_000_000},
                ]
            }

        payload = ollama_support.status(fetcher=live_fetcher)
        assert payload["server_running"] is True
        assert payload["models"][0]["name"] == "qwen2.5:7b"
        assert payload["models"][0]["size_gb"] == 4.4

    def test_pull_spawns_detached_download(self, monkeypatch):
        commands = []
        monkeypatch.setattr(
            ollama_support,
            "cli_available",
            lambda which=None: True,
        )
        result = ollama_support.start_pull(
            "qwen2.5:7b", spawner=commands.append
        )
        assert result["started"] is True
        assert commands == [["ollama", "pull", "qwen2.5:7b"]]

    def test_pull_without_cli_explains(self, monkeypatch):
        monkeypatch.setattr(
            ollama_support,
            "cli_available",
            lambda which=None: False,
        )
        result = ollama_support.start_pull("qwen2.5:7b")
        assert result["started"] is False
        assert "ollama.com" in result["reason"]


class TestModelInfo:
    def test_reports_context_size_and_quantization(self):
        def fake(url, payload, timeout):
            assert url.endswith("/api/show")
            assert payload == {"name": "qwen2.5:7b"}
            return {
                "details": {
                    "parameter_size": "7.6B",
                    "quantization_level": "Q4_K_M",
                    "family": "qwen2",
                },
                "model_info": {"qwen2.context_length": 32768},
            }

        info = ollama_support.model_info("qwen2.5:7b", transport=fake)
        assert info["available"] is True
        assert info["context_length"] == 32768
        assert info["parameter_size"] == "7.6B"
        assert info["quantization"] == "Q4_K_M"

    def test_unavailable_when_server_is_down(self):
        def dead(url, payload, timeout):
            raise OSError("connection refused")

        assert ollama_support.model_info("x", transport=dead) == {
            "available": False,
        }

    def test_show_endpoint_returns_model_info(
        self, offline_router, monkeypatch
    ):
        monkeypatch.setattr(
            ollama_support,
            "model_info",
            lambda model: {"available": True, "context_length": 8192},
        )
        payload = ok(
            offline_router,
            "POST",
            "/assistant/ollama/show",
            {"model": "llama3.1:8b"},
        )
        assert payload["context_length"] == 8192


def test_gemini_save_restart_restore_flow(api_app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paios.api.ai_settings.protect_key", lambda x: "dpapi:" + x
    )
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key",
        lambda x: x.replace("dpapi:", "") if x.startswith("dpapi:") else None,
    )

    # 1. Mock Gemini transport to succeed
    def fake_gemini_transport(url, payload, headers, timeout):
        if "generateContent" in url:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"answer": "Hi, I am Gemini.", "bullets": [], "confidence": 1.0}'
                                }
                            ]
                        }
                    }
                ]
            }
        return {}

    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport",
        fake_gemini_transport,
    )
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # 2. Build initial router (no assistant active initially)
    router1 = ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=None,
        assistant_provider="none",
        ai_dir=ai_dir,
    )

    # 3. Save Gemini provider, model, and API key via PUT config
    put_payload = ok(
        router1,
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "api_key": "my-secret-gemini-key",
        },
    )
    assert put_payload["available"] is True
    assert put_payload["provider"] == "gemini"

    # 4. Simulate a restart: load from settings just like server.py does
    stored = ai_settings.load(ai_dir)
    assert stored.get("provider") == "gemini"
    assert stored.get("model") == "gemini-2.5-pro"

    # Verify the key is stored protected and can be retrieved
    stored_key = ai_settings.api_key_for(ai_dir, "gemini")
    assert stored_key == "my-secret-gemini-key"

    # Compose assistant for the new startup instance
    provider_default = stored.get("provider")
    model_default = stored.get("model")
    resolved = assistant_support.resolve_provider(provider_default)
    (
        restored_provider,
        restored_assistant,
        restored_reason,
    ) = assistant_support.compose_assistant(
        provider_default,
        model_default,
        api_key=ai_settings.api_key_for(ai_dir, resolved),
        data_dir=ai_dir,
    )
    assert restored_provider == "gemini"
    assert restored_assistant is not None
    assert "gemini adapter ready" in restored_reason.lower()

    # Build router2 (representing the restarted server)
    router2 = ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=restored_assistant,
        assistant_provider=restored_provider,
        assistant_reason=restored_reason,
        ai_dir=ai_dir,
    )

    # 5. Verify the saved provider and model are reflected in GET config
    config_payload = ok(router2, "GET", "/assistant/config")
    assert config_payload["provider"] == "gemini"
    assert config_payload["model"] == "gemini-2.5-pro"
    assert config_payload["available"] is True
    assert config_payload["stored_keys"]["gemini"] is True

    # 6. Verify Gemini actually receives the API key and is used for an AI request
    test_payload = ok(router2, "POST", "/assistant/test", {})
    print("TEST PAYLOAD WAS:", test_payload)
    assert test_payload["ok"] is True
    assert test_payload["source"] == "llm"
    assert test_payload["adapter"] == "gemini:gemini-2.5-pro"
    assert test_payload["answer"] == "Hi, I am Gemini."


def test_cloud_provider_environment_variable_fallback(api_app, tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret-key")

    # 1. Mock Gemini transport to succeed
    def fake_gemini_transport(url, payload, headers, timeout):
        if "generateContent" in url:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"answer": "Hi from env.", "bullets": [], "confidence": 1.0}'
                                }
                            ]
                        }
                    }
                ]
            }
        return {}

    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport",
        fake_gemini_transport,
    )
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Store provider selection but NO key is stored (simulating missing DPAPI)
    ai_settings.save(ai_dir, {"provider": "gemini", "model": "gemini-2.5-pro"})

    # Compose assistant for the startup instance
    stored = ai_settings.load(ai_dir)
    provider_default = stored.get("provider")
    model_default = stored.get("model")
    resolved = assistant_support.resolve_provider(provider_default)
    (
        restored_provider,
        restored_assistant,
        restored_reason,
    ) = assistant_support.compose_assistant(
        provider_default,
        model_default,
        api_key=ai_settings.api_key_for(ai_dir, resolved),  # This will be None
        data_dir=ai_dir,
    )
    assert restored_provider == "gemini"
    assert restored_assistant is not None
    assert "gemini adapter ready" in restored_reason.lower()


def test_gemini_falls_back_to_ollama_when_available(api_app, tmp_path, monkeypatch):
    # If Gemini is available but throws an error during complete(), it should fall back to Ollama
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)

    # 1. Mock Gemini transport to fail
    def failing_gemini(url, payload, headers, timeout):
        import urllib.error
        raise urllib.error.HTTPError(url, 500, "Gemini quota exceeded", {}, None)

    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport", failing_gemini
    )

    # Mock Ollama transport to succeed so Ollama is available
    def succeeding_ollama(url, payload, timeout):
        if "chat" in url:
            return {"message": {"content": "{\"answer\": \"Hi from Ollama fallback.\", \"bullets\": [], \"confidence\": 1.0}"}}
        return {"version": "0.1.0"}

    monkeypatch.setattr(
        "paios.assistant.adapters.ollama.default_transport", succeeding_ollama
    )

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Store key for Gemini so it is available
    ai_settings.store_api_key(ai_dir, "gemini", "my-key")

    # Compose assistant
    provider, assistant, reason = assistant_support.compose_assistant(
        "gemini", "gemini-2.5-flash", api_key="my-key", data_dir=ai_dir
    )
    assert provider == "gemini"
    assert assistant is not None
    assert "gemini adapter ready" in reason

    # Call completion and check that it falls back to Ollama!
    res = assistant.answer_question("test prompt")
    assert res.answer == "Hi from Ollama fallback."


def test_gemini_fallback_with_missing_dpapi(api_app, tmp_path, monkeypatch):
    # Simulate non-Windows environment where DPAPI fails/returns None
    monkeypatch.setattr(
        "paios.api.ai_settings.protect_key", lambda x: None
    )
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key", lambda x: None
    )

    # Mock Gemini transport to succeed
    def fake_gemini_transport(url, payload, headers, timeout):
        if "generateContent" in url:
            return {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": '{"answer": "Hi, I am Gemini.", "bullets": [], "confidence": 1.0}'
                                }
                            ]
                        }
                    }
                ]
            }
        return {}

    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport",
        fake_gemini_transport,
    )
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Build router (no assistant active initially)
    router = ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=None,
        assistant_provider="none",
        ai_dir=ai_dir,
    )

    # 1. Put config with api_key. Since protect_key is mocked to return None,
    # store_api_key will fail to store it, but the live recomposed assistant
    # should still succeed because it falls back to using the provided api_key!
    put_payload = ok(
        router,
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-pro",
            "api_key": "my-secret-gemini-key",
        },
    )

    # It should show available because the live composition succeeded with the supplied api_key
    assert put_payload["available"] is True
    assert put_payload["provider"] == "gemini"
    assert "warning" in put_payload  # contains the warning about secure key storage being unavailable

    # Test the connection live - it should succeed using the supplied key
    test_payload = ok(router, "POST", "/assistant/test", {})
    assert test_payload["ok"] is True
    assert test_payload["adapter"] == "gemini:gemini-2.5-pro"

    # 2. Verify environment fallback on startup when no key is in settings.
    # Set the environment variable fallback.
    monkeypatch.setenv("GEMINI_API_KEY", "env-secret-key")

    # Try composing without passing a key explicitly.
    # It should fall back to GEMINI_API_KEY and succeed!
    (
        restored_provider,
        restored_assistant,
        restored_reason,
    ) = assistant_support.compose_assistant(
        "gemini",
        "gemini-2.5-pro",
        api_key=None,
        data_dir=ai_dir,
    )
    assert restored_provider == "gemini"
    assert restored_assistant is not None
    assert "gemini adapter ready" in restored_reason.lower()

def test_assistant_config_endpoints_warnings_on_non_windows(api_app, tmp_path, monkeypatch):
    # Mock os.name to be non-Windows ("posix") and mock key protection to fail
    monkeypatch.setattr("os.name", "posix")
    monkeypatch.setattr("paios.api.ai_settings.protect_key", lambda x: None)
    monkeypatch.setattr("paios.api.ai_settings.unprotect_key", lambda x: None)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)
    ai_settings.save(ai_dir, {"provider": "gemini", "model": "gemini-2.5-flash"})

    router = ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=None,
        assistant_provider="none",
        ai_dir=ai_dir,
    )

    # 1. Test GET config endpoint
    get_status, get_payload = router.handle("GET", "/assistant/config")
    assert get_status == 200
    assert "warning" in get_payload
    assert "Secure key storage is unavailable on this platform" in get_payload["warning"]
    assert "export GEMINI_API_KEY=" in get_payload["warning"]

    # 2. Test PUT config endpoint
    put_status, put_payload = router.handle(
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "some-secret-key"
        }
    )
    assert put_status == 200
    assert "warning" in put_payload
    assert "Secure key storage is unavailable on this platform" in put_payload["warning"]
    assert "export GEMINI_API_KEY=" in put_payload["warning"]


def test_gemini_test_connection_failures(api_app, tmp_path, monkeypatch):
    monkeypatch.setattr(
        "paios.api.ai_settings.protect_key", lambda x: "dpapi:" + x
    )
    monkeypatch.setattr(
        "paios.api.ai_settings.unprotect_key",
        lambda x: x.replace("dpapi:", "") if x.startswith("dpapi:") else None,
    )
    monkeypatch.delenv("PAIOS_AI_PROVIDER", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ai_dir = tmp_path / "ai-data"
    ai_dir.mkdir(parents=True, exist_ok=True)

    # Mock Ollama transport to return a successful Ollama response
    def succeeding_ollama(url, payload, timeout):
        if "chat" in url:
            return {"message": {"content": "{\"answer\": \"Hi from Ollama fallback.\", \"bullets\": [], \"confidence\": 1.0}"}}
        return {"version": "0.1.0"}

    monkeypatch.setattr(
        "paios.assistant.adapters.ollama.default_transport", succeeding_ollama
    )

    # 1. Missing Key Scenario
    # Configure Gemini with no key
    router1 = ApiRouter(
        api_app,
        planning=PlanningService(tmp_path / "planning-data"),
        backups=BackupManager(tmp_path / "data", tmp_path / "backups"),
        assistant=None,
        assistant_provider="none",
        ai_dir=ai_dir,
    )
    put_status, put_payload = router1.handle(
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": ""
        }
    )
    # The active assistant has Gemini but without a key
    test_status, test_payload = router1.handle("POST", "/assistant/test", {})
    assert test_status == 200
    assert test_payload["ok"] is False
    assert test_payload["source"] == "llm"
    assert "could not be initialized" in test_payload["answer"].lower() or "missing" in test_payload["answer"].lower()

    # 2. Invalid Key Scenario
    # Mock Gemini transport to return 401 Unauthorized
    def failing_gemini_401(url, payload, headers, timeout):
        import urllib.error
        raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, None)

    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport", failing_gemini_401
    )

    # Configure Gemini with a key (so it initializes successfully)
    # Live-recompose will build the orchestrator
    put_status, put_payload = router1.handle(
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "invalid-gemini-key"
        }
    )
    assert put_payload["available"] is True

    # Test connection. It should call Gemini and fail, rather than falling back to Ollama!
    test_status, test_payload = router1.handle("POST", "/assistant/test", {})
    assert test_status == 200
    assert test_payload["ok"] is False
    assert test_payload["source"] == "llm"
    assert "Invalid API Key" in test_payload["answer"]

    # 3. HTTP/API Failure (Quota Exceeded 429) Scenario
    # Mock Gemini transport to return 429 Too Many Requests
    def failing_gemini_429(url, payload, headers, timeout):
        import urllib.error
        raise urllib.error.HTTPError(url, 429, "Too Many Requests", {}, None)

    monkeypatch.setattr(
        "paios.assistant.adapters.gemini.default_transport", failing_gemini_429
    )

    # Force recomposition so GeminiProvider gets the new default_transport mock
    router1.handle(
        "PUT",
        "/assistant/config",
        {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "invalid-gemini-key"
        }
    )

    test_status, test_payload = router1.handle("POST", "/assistant/test", {})
    assert test_status == 200
    assert test_payload["ok"] is False
    assert test_payload["source"] == "llm"
    assert "Quota exceeded" in test_payload["answer"]


