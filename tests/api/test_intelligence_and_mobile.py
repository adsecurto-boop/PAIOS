"""The intelligence layer and the mobile companion API.

Covers: AI settings persistence + live recomposition, hardware-driven
model recommendation, the daily-rhythm workflows in BOTH paths (LLM via
the null adapter, deterministic without one), and the /mobile namespace
(pairing, token auth, loopback-only administration, offline-queue
idempotency). No network anywhere.
"""

from pathlib import Path

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
                c
                for c in hardware.recommend_models(float(ram))
                if c.recommended
            ]
            assert len(recommended) == 1, f"ram={ram}"

    def test_detect_never_raises(self):
        profile = hardware.detect()
        assert profile.cpu_cores >= 1
        assert profile.ram_gb >= 0.0


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
            offline_router, "PUT", "/assistant/config",
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
            offline_router, "POST", "/assistant/morning-plan",
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
            ai_router, "POST", "/assistant/morning-plan",
            {"mood": "good"},
        )
        assert payload["source"] == "llm"
        assert payload["adapter"] == "null"
        assert "timeline" in payload and "risks" in payload

    def test_evening_review_heuristic_counts_today(self, offline_router):
        payload = ok(
            offline_router, "POST", "/assistant/evening-review",
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
        router, "POST", "/mobile/pair",
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
            offline_router, "GET", "/mobile/timeline",
            headers=bearer(token),
        )
        assert "entries" in payload and "server_time" in payload

    def test_wrong_code_is_rejected(self, offline_router):
        ok(offline_router, "POST", "/mobile/pairing/start")
        status, _ = offline_router.handle(
            "POST", "/mobile/pair", {"code": "000000", "device_name": "x"}
        )
        assert status == 401

    def test_code_is_single_use(self, offline_router):
        started = ok(offline_router, "POST", "/mobile/pairing/start")
        ok(
            offline_router, "POST", "/mobile/pair",
            {"code": started["code"]}, expect=201,
        )
        status, _ = offline_router.handle(
            "POST", "/mobile/pair", {"code": started["code"]}
        )
        assert status == 401

    def test_unpaired_requests_are_401(self, offline_router):
        for path in (
            "/mobile/timeline", "/mobile/tasks", "/mobile/logs",
            "/mobile/study",
        ):
            status, _ = offline_router.handle("GET", path)
            assert status == 401, path

    def test_pairing_admin_is_loopback_only(self, offline_router):
        status, _ = offline_router.handle(
            "POST", "/mobile/pairing/start", None,
            client_host="192.168.1.50",
        )
        assert status == 403
        # The phone-facing half is NOT loopback-restricted.
        started = ok(offline_router, "POST", "/mobile/pairing/start")
        ok(
            offline_router, "POST", "/mobile/pair",
            {"code": started["code"]},
            expect=201, client_host="192.168.1.50",
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
            offline_router, "DELETE",
            f"/mobile/pairing/devices/{device_id}",
        )
        status, _ = offline_router.handle(
            "GET", "/mobile/timeline", None, headers=bearer(token)
        )
        assert status == 401

    def test_auth_endpoint_validates_tokens(self, offline_router):
        token = pair_device(offline_router)
        payload = ok(
            offline_router, "POST", "/mobile/auth", {"token": token}
        )
        assert payload["valid"] is True
        status, _ = offline_router.handle(
            "POST", "/mobile/auth", {"token": "bogus"}
        )
        assert status == 401


class TestMobileData:
    def test_tasks_roundtrip(self, offline_router):
        token = pair_device(offline_router)
        created = ok(
            offline_router, "POST", "/mobile/tasks",
            {"title": "From the phone"},
            expect=201, headers=bearer(token),
        )
        assert created["materialized"] in (True, False)
        events = ok(
            offline_router, "GET", "/mobile/tasks", headers=bearer(token)
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
            offline_router, "POST", "/mobile/logs", entry,
            expect=201, headers=bearer(token),
        )
        second = ok(
            offline_router, "POST", "/mobile/logs", entry,
            expect=201, headers=bearer(token),
        )
        assert first["id"] == second["id"]  # duplicate suppressed
        entries = ok(
            offline_router, "GET", "/mobile/logs", headers=bearer(token)
        )["entries"]
        assert len(
            [e for e in entries if e["client_id"] == "phone-abc-1"]
        ) == 1

    def test_logs_filter_by_day_segment(self, offline_router):
        token = pair_device(offline_router)
        record = ok(
            offline_router, "POST", "/mobile/logs",
            {"kind": "mood", "text": "good"},
            expect=201, headers=bearer(token),
        )
        day = record["day"]
        payload = ok(
            offline_router, "GET", f"/mobile/logs/{day}",
            headers=bearer(token),
        )
        assert all(entry["day"] == day for entry in payload["entries"])
        assert payload["entries"]

    def test_study_endpoint_serves_knowledge_and_logs(self, offline_router):
        token = pair_device(offline_router)
        ok(
            offline_router, "POST", "/mobile/logs",
            {"kind": "study", "text": "reviewed DDD chapter 4"},
            expect=201, headers=bearer(token),
        )
        payload = ok(
            offline_router, "GET", "/mobile/study", headers=bearer(token)
        )
        assert "knowledge" in payload
        assert payload["study_logs"][0]["text"].startswith("reviewed")

    def test_assistant_query_falls_back_without_ai(self, offline_router):
        token = pair_device(offline_router)
        payload = ok(
            offline_router, "POST", "/mobile/assistant/query",
            {"text": "how is my week?"}, headers=bearer(token),
        )
        assert payload["source"] == "heuristic"

    def test_assistant_query_uses_llm_when_available(self, ai_router):
        token = pair_device(ai_router)
        payload = ok(
            ai_router, "POST", "/mobile/assistant/query",
            {"text": "how is my week?"}, headers=bearer(token),
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
            ollama_support, "cli_available", lambda which=None: True
        )
        result = ollama_support.start_pull(
            "qwen2.5:7b", spawner=commands.append
        )
        assert result["started"] is True
        assert commands == [["ollama", "pull", "qwen2.5:7b"]]

    def test_pull_without_cli_explains(self, monkeypatch):
        monkeypatch.setattr(
            ollama_support, "cli_available", lambda which=None: False
        )
        result = ollama_support.start_pull("qwen2.5:7b")
        assert result["started"] is False
        assert "ollama.com" in result["reason"]
