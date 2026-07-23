"""Error translation, live HTTP server, delegation, forbidden imports."""

import ast
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import paios.api as api_package
from paios.api import ApiConfig, ApiRouter, ApiServer
from paios.application.application import Application
from paios.application.config import ApplicationConfig


class TestErrorTranslation:
    def test_unknown_route_is_404(self, router):
        status, payload = router.handle("GET", "/nonsense")
        assert status == 404
        assert payload["error"]["type"] == "ApiError"

    def test_wrong_method_is_405(self, router):
        status, payload = router.handle("POST", "/status")
        assert status == 405
        status, _ = router.handle("GET", "/tick")
        assert status == 405

    def test_missing_field_is_400(self, router):
        status, payload = router.handle("POST", "/goals", {})
        assert status == 400
        assert "'name'" in payload["error"]["message"]

    def test_wrong_type_is_400(self, router):
        status, payload = router.handle(
            "POST", "/goals", {"name": 42}
        )
        assert status == 400

    def test_non_object_body_is_400(self, router):
        status, payload = router.handle("POST", "/goals", ["not", "an", "obj"])
        assert status == 400

    def test_unknown_entity_is_404(self, router):
        status, payload = router.handle("POST", "/goals/missing/complete")
        assert status == 404
        assert payload["error"]["type"] == "EntityNotFound"

    def test_unknown_event_is_404(self, router):
        status, _ = router.handle("GET", "/events/missing")
        assert status == 404

    def test_duplicate_is_409(self, router):
        assert router.handle("POST", "/goals", {"name": "Twice"})[0] == 201
        status, payload = router.handle("POST", "/goals", {"name": "Twice"})
        assert status == 409
        assert payload["error"]["type"] == "DuplicateEntityError"

    def test_domain_validation_is_400(self, router):
        status, payload = router.handle(
            "POST",
            "/knowledge",
            {
                "domain": "X",
                "topic": "Y",
                "concept": "Z",
                "confidence": 150,
            },
        )
        assert status == 400
        assert payload["error"]["type"] == "DomainValidationError"

    def test_invariant_violation_is_409(self, router, api_app):
        resources = api_app.list_resources()
        resource_id = str(resources[0].resource_id)
        status, payload = router.handle(
            "POST", f"/resources/{resource_id}/consume", {"amount": 999}
        )
        assert status == 409
        assert payload["error"]["type"] == "InvariantViolationError"

    def test_invalid_transition_is_409(self, router):
        from tests.api.conftest import materialize_event

        event_id = materialize_event(router)
        status, payload = router.handle("POST", f"/events/{event_id}/pause")
        assert status == 409  # cannot pause a Scheduled (not running) event

    def test_not_started_application_is_503(self, tmp_path):
        application = Application(
            ApplicationConfig(data_dir=tmp_path / "data")
        )
        router = ApiRouter(application)  # never started
        status, payload = router.handle("GET", "/status")
        assert status == 503
        assert payload["error"]["type"] == "ApplicationNotStartedError"

    def test_bad_enum_is_400(self, router):
        status, payload = router.handle(
            "POST",
            "/resources",
            {"type": "mana", "current_value": 1, "unit": "points"},
        )
        assert status == 400
        assert "must be one of" in payload["error"]["message"]


class TestLiveServer:
    """The real socket server: stdlib client against stdlib server."""

    @pytest.fixture
    def live(self, api_app):
        server = ApiServer(
            ApiConfig(port=0), application=api_app
        )  # port 0 -> ephemeral
        server.start()
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{server.port}"
        server.shutdown()
        thread.join(timeout=5)

    def _get(self, url):
        with urllib.request.urlopen(url) as response:
            return response.status, json.loads(response.read().decode())

    def _post(self, url, body=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read().decode())

    def test_get_status_over_http(self, live):
        status, payload = self._get(live + "/status")
        assert status == 200
        assert payload["state"] == "Running"

    def test_post_goal_over_http(self, live):
        status, payload = self._post(live + "/goals", {"name": "Via HTTP"})
        assert status == 201
        assert payload["name"] == "Via HTTP"

    def test_error_status_over_http(self, live):
        with pytest.raises(urllib.error.HTTPError) as failure:
            self._get(live + "/nonsense")
        assert failure.value.code == 404
        body = json.loads(failure.value.read().decode())
        assert body["error"]["type"] == "ApiError"

    def test_invalid_json_body_is_400(self, live):
        request = urllib.request.Request(
            live + "/goals",
            data=b"{not json",
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as failure:
            urllib.request.urlopen(request)
        assert failure.value.code == 400

    def test_shutdown_stops_owned_application_only(self, api_app):
        server = ApiServer(ApiConfig(port=0), application=api_app)
        server.start()
        server.shutdown()
        # Injected applications are left running (the caller owns them).
        assert api_app.started is True


class TestDelegation:
    def test_router_touches_only_the_facade(self, router):
        # M20 (approved): the router holds the facade plus the additive
        # planning/backup/assistant collaborators — nothing else, and the
        # assistant is proposal/explanation-only by construction.
        assert set(vars(router)) == {
            "_app",
            "_planning",
            "_backups",
            "_assistant",
            "_assistant_provider",
            "_assistant_reason",
            "_mobile",
            "_ai_dir",
            "_network_dir",
            "_bound_host",
            "_bound_port",
            "_discovery",
            "_relay_status",
            "_relay_reload",
            "_relay_authorize",
            "_request_headers",
            "_request_client",
        }

    def test_actions_delegate_to_facade_methods(self, api_app):
        calls = []

        class Recorder:
            def __getattr__(self, name):
                def call(*args, **kwargs):
                    calls.append(name)
                    if name.startswith("list_"):
                        return []
                    return None

                return call

        router = ApiRouter(Recorder())
        router.handle("POST", "/goals", {"name": "X", "user_id": "u1"})
        assert calls == ["add_goal"]
        calls.clear()
        router.handle("POST", "/events/e1/start", None)
        assert calls == ["start_event"]


FORBIDDEN_PREFIXES = (
    "paios.runtime",
    "paios.scheduler",
    "paios.decision_engine",
    "paios.learning",
    "paios.infrastructure",
    "paios.daemon",
    "paios.cli",
    "paios.dashboard",
    "paios.repositories.json",
    "paios.repositories.factory",
    "paios.repositories.serialization",
    "paios.domain.entities",
    "paios.domain.services",
    "paios.domain.state_machines",
)

ALLOWED_PAIOS_PREFIXES = (
    "paios.api",
    "paios.application",
    "paios.domain.enums",
    "paios.domain.errors",
    "paios.domain.value_objects",
    "paios.repositories.errors",
    # M20 (approved additive surface): planning stores/service, the
    # assistant language layer (proposal + explanation only), and the
    # system backup manager for the /backups wrapper. The Scheduler,
    # Runtime, Decision Engine and Learning Engine remain forbidden.
    "paios.planning",
    "paios.assistant",
    "paios.system.backup",
    # Intelligence layer (additive): hardware detection feeds the AI
    # setup surface (model recommendations) — read-only probes only.
    "paios.system.hardware",
    # M21 (additive): the Networking page's facts + persisted access
    # mode + firewall helper — read-only probes and one settings file.
    "paios.system.network",
    # M22 (additive): the mDNS advertiser started in Local Network mode.
    "paios.system.discovery",
    # M23 (additive): the outbound relay connector (remote access).
    "paios.system.relay_client",
)


class TestForbiddenImports:
    def test_api_imports_only_facade_stdlib_and_parsing_types(self):
        package_dir = Path(api_package.__file__).parent
        for module_path in package_dir.glob("*.py"):
            tree = ast.parse(module_path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                names = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [node.module or ""]
                for name in names:
                    assert not name.startswith(FORBIDDEN_PREFIXES), (
                        f"{module_path.name} imports forbidden {name!r}"
                    )
                    if name.startswith("paios"):
                        assert name.startswith(ALLOWED_PAIOS_PREFIXES), (
                            f"{module_path.name} imports {name!r}"
                        )
