"""Route table and dispatch: HTTP verb + path -> one facade call.

Every handler performs exactly one primary delegation into the
Application facade (list/get resolution reads are input handling, the
M8/M10 CLI convention). Handlers never decide anything — they parse,
delegate, serialize.

Identifier and enum types are imported from the domain for request
PARSING only — the same established convention the CLI uses. No runtime,
scheduler, decision-engine, learning, or repository-implementation
module is imported.
"""

import os
from datetime import timedelta

from paios.application.application import Application
from paios.domain.enums import (
    DisturberSeverity,
    DisturberType,
    ResourceType,
)
from paios.domain.value_objects.identifiers import (
    EventId,
    GoalId,
    ProjectId,
    RecommendationId,
    ResourceId,
    UserId,
)
from paios.api import (
    ai_settings,
    assistant_support,
    mobile_support,
    ollama_support,
    schemas,
    serialization,
)
from paios.api.errors import ApiError, translate
from paios.planning.service import PlanningService
from paios.system.backup import BackupManager

#: Fallback owner when the store holds no users (the CLI convention).
DEFAULT_USER_ID = "user_001"


class ApiRouter:
    """Pure request core: (method, path, body) -> (status, payload).

    No sockets, no streams — the HTTP server binds this to the wire;
    tests call it directly.

    M20 additive collaborators (all optional, so existing constructions
    keep working): the PlanningService (inbox/templates/recurrences/
    metadata), a BackupManager, and an AssistantOrchestrator (None ->
    deterministic fallbacks answer the assistant routes).
    """

    def __init__(
        self,
        application: Application,
        planning: PlanningService | None = None,
        backups: BackupManager | None = None,
        assistant=None,
        assistant_provider: str = "none",
        assistant_reason: str | None = None,
        mobile=None,
        ai_dir=None,
    ) -> None:
        self._app = application
        self._planning = planning
        self._backups = backups
        self._assistant = assistant
        self._assistant_provider = assistant_provider
        self._assistant_reason = (
            assistant_reason
            if assistant_reason is not None
            else (
                f"{assistant_provider} adapter ready"
                if assistant is not None
                else "no AI provider configured: "
                + assistant_support.CONFIG_HINT
            )
        )
        #: Mobile companion collaborators (None -> /mobile 503s).
        self._mobile = mobile
        #: Where ai-settings.json lives (None -> settings routes 503).
        self._ai_dir = ai_dir
        # Per-request transport context. The HTTP server is deliberately
        # single-threaded (see server.py), so stashing per request is
        # safe; tests calling handle() directly are sequential too.
        self._request_headers: dict | None = None
        self._request_client: str | None = None

    def _require_planning(self) -> PlanningService:
        if self._planning is None:
            raise ApiError(503, "Planning services are not composed")
        return self._planning

    def _require_backups(self) -> BackupManager:
        if self._backups is None:
            raise ApiError(503, "Backup services are not composed")
        return self._backups

    # --- dispatch --------------------------------------------------------

    def handle(
        self,
        method: str,
        path: str,
        body=None,
        headers: dict | None = None,
        client_host: str | None = None,
    ) -> tuple[int, dict]:
        self._request_headers = headers
        self._request_client = client_host
        try:
            return self._dispatch(method.upper(), path, body)
        except Exception as error:  # translated, never propagated
            return translate(error)
        finally:
            self._request_headers = None
            self._request_client = None

    def _dispatch(self, method: str, path: str, body) -> tuple[int, dict]:
        segments = tuple(
            segment for segment in path.strip("/").split("/") if segment
        )
        matched_any_path = False
        for route_method, pattern, handler in _ROUTES:
            params = _match(pattern, segments)
            if params is None:
                continue
            matched_any_path = True
            if route_method != method:
                continue
            return handler(self, params, schemas.body_object(body))
        if matched_any_path:
            raise ApiError(405, f"Method {method} not allowed for /{path.strip('/')}")
        raise ApiError(404, f"Unknown route: /{'/'.join(segments)}")

    # --- system ----------------------------------------------------------

    def _get_status(self, params, body):
        return 200, serialization.serialize_status(self._app.status())

    def _get_snapshot(self, params, body):
        snapshot = serialization.serialize_snapshot(self._app.snapshot())
        if snapshot is None:
            raise ApiError(404, "No snapshot available")
        return 200, snapshot

    def _post_tick(self, params, body):
        result = serialization.serialize_decision_result(self._app.tick())
        # M20 additive field: due recurrence rules expand into proposed
        # intents on the same cadence as the loop pass.
        result["recurrences_expanded"] = self._expand_due_recurrences()
        return 200, result

    # --- recommendations -------------------------------------------------

    def _get_recommendations(self, params, body):
        return 200, {
            "recommendations": [
                serialization.serialize_recommendation(r)
                for r in self._app.active_recommendations()
            ]
        }

    def _post_recommendation_accept(self, params, body):
        self._app.accept_recommendation(RecommendationId(params["id"]))
        return 200, {"result": "accepted"}

    def _post_recommendation_reject(self, params, body):
        self._app.reject_recommendation(
            RecommendationId(params["id"]),
            reason=schemas.optional_string(body, "reason"),
        )
        return 200, {"result": "rejected"}

    # --- events ----------------------------------------------------------

    def _get_events(self, params, body):
        return 200, {
            "events": [
                serialization.serialize_event(event)
                for event in self._app.list_events()
            ]
        }

    def _get_event(self, params, body):
        wanted = params["id"]
        for event in self._app.list_events():
            if str(event.event_id) == wanted:
                return 200, serialization.serialize_event(event)
        raise ApiError(404, f"Event {wanted!r} not found")

    def _post_event_start(self, params, body):
        self._app.start_event(EventId(params["id"]))
        return 200, {"result": "started"}

    def _post_event_pause(self, params, body):
        self._app.pause_event(EventId(params["id"]))
        return 200, {"result": "paused"}

    def _post_event_resume(self, params, body):
        self._app.resume_event(EventId(params["id"]))
        return 200, {"result": "resumed"}

    def _post_event_complete(self, params, body):
        self._app.complete_event(
            EventId(params["id"]),
            actual_outcome=schemas.optional_string(body, "actual_outcome"),
        )
        return 200, {"result": "completed"}

    def _post_event_cancel(self, params, body):
        self._app.cancel_event(
            EventId(params["id"]),
            reason=schemas.optional_string(body, "reason"),
        )
        return 200, {"result": "cancelled"}

    def _post_event_archive(self, params, body):
        # M15 approved correction: the mobile client's Archive action.
        self._app.archive_event(EventId(params["id"]))
        return 200, {"result": "archived"}

    # --- events: M20 user-authored intents ---------------------------------
    # Creation rides the approved pipeline: intent -> Recommendation ->
    # admit -> accept -> the Scheduler materializes. Handlers parse,
    # delegate, serialize — the Scheduler stays the scheduling authority.

    def _post_events(self, params, body):
        title = schemas.require_string(body, "title")
        mode = schemas.optional_string(body, "mode") or "planned"
        metadata = schemas.optional_object(body, "metadata")
        if mode == "now":
            event = self._app.report_spontaneous_action(
                self._owner(body),
                schemas.optional_string(body, "category") or "spontaneous",
                title,
            )
            self._store_metadata(str(event.event_id), metadata)
            return 201, serialization.serialize_event(event)
        if mode != "planned":
            raise ApiError(400, "Field 'mode' must be 'planned' or 'now'")
        recommendation, event_id = self._app.propose_user_event(
            self._owner(body),
            title,
            suggested_time=schemas.optional_datetime(body, "suggested_time"),
            priority=schemas.optional_number(body, "priority"),
            project_id=self._optional_project(body),
            expected_outcome=schemas.optional_string(body, "expected_outcome"),
        )
        self._store_metadata(
            str(event_id) if event_id is not None
            else str(recommendation.recommendation_id),
            metadata,
        )
        return 201, serialization.serialize_proposed(recommendation, event_id)

    def _put_event(self, params, body):
        old_id = params["id"]
        recommendation, event_id = self._app.edit_event(
            EventId(old_id),
            self._owner(body),
            schemas.require_string(body, "title"),
            suggested_time=schemas.optional_datetime(body, "suggested_time"),
            priority=schemas.optional_number(body, "priority"),
            project_id=self._optional_project(body),
            expected_outcome=schemas.optional_string(body, "expected_outcome"),
        )
        if self._planning is not None:
            new_key = (
                str(event_id) if event_id is not None
                else str(recommendation.recommendation_id)
            )
            self._planning.metadata.relink(old_id, new_key)
            self._store_metadata(
                new_key, schemas.optional_object(body, "metadata")
            )
        return 200, serialization.serialize_proposed(recommendation, event_id)

    def _post_event_duplicate(self, params, body):
        source_id = params["id"]
        recommendation, event_id = self._app.duplicate_event(
            EventId(source_id),
            suggested_time=schemas.optional_datetime(body, "suggested_time"),
        )
        if self._planning is not None:
            source_meta = self._planning.metadata.get(source_id)
            if source_meta is not None:
                copied = {
                    field: source_meta[field]
                    for field in self._planning.metadata.FIELDS
                    if field in source_meta
                }
                self._store_metadata(
                    str(event_id) if event_id is not None
                    else str(recommendation.recommendation_id),
                    copied,
                )
        return 201, serialization.serialize_proposed(recommendation, event_id)

    def _get_event_metadata(self, params, body):
        record = self._require_planning().metadata.resolve(params["id"])
        return 200, record if record is not None else {"key": params["id"]}

    def _put_event_metadata(self, params, body):
        record = self._require_planning().metadata.set(
            params["id"], schemas.body_object(body), self._app.current_time()
        )
        return 200, record

    # --- plan / timeline (M20) ---------------------------------------------

    def _get_plan(self, params, body):
        return 200, serialization.serialize_plan(self._app.plan())

    # --- templates (M20) -----------------------------------------------------

    def _get_templates(self, params, body):
        return 200, {"templates": self._require_planning().templates.list()}

    def _post_templates(self, params, body):
        record = self._require_planning().templates.add(
            schemas.require_string(body, "name"),
            schemas.require_string(body, "title"),
            self._app.current_time(),
            category=schemas.optional_string(body, "category") or "planned",
            metadata=schemas.optional_object(body, "metadata"),
        )
        return 201, record

    def _delete_template(self, params, body):
        self._require_planning().templates.delete(params["id"])
        return 200, {"result": "deleted"}

    def _post_template_instantiate(self, params, body):
        planning = self._require_planning()
        intent, default_metadata = planning.instantiate_template(
            params["id"],
            self._owner(body),
            schemas.optional_datetime(body, "suggested_time"),
            priority=schemas.optional_number(body, "priority"),
        )
        recommendation, event_id = self._app.propose_user_event(
            intent.user_id,
            intent.title,
            suggested_time=intent.suggested_time,
            priority=intent.priority,
        )
        self._store_metadata(
            str(event_id) if event_id is not None
            else str(recommendation.recommendation_id),
            default_metadata or None,
        )
        return 201, serialization.serialize_proposed(recommendation, event_id)

    # --- recurrences (M20) ----------------------------------------------------

    def _get_recurrences(self, params, body):
        return 200, {
            "recurrences": self._require_planning().recurrences.list()
        }

    def _post_recurrences(self, params, body):
        planning = self._require_planning()
        now = self._app.current_time()
        explicit_first = schemas.optional_datetime(body, "first_run")
        record = planning.recurrences.add(
            schemas.require_string(body, "title"),
            schemas.require_string(body, "time_of_day"),
            schemas.require_string_list(body, "days"),
            explicit_first if explicit_first is not None else now,
            now,
            category=schemas.optional_string(body, "category") or "recurring",
            metadata=schemas.optional_object(body, "metadata"),
        )
        if explicit_first is None:
            record = planning.recurrences.set_next_run(
                record["id"], planning.next_occurrence(record, now)
            )
        return 201, record

    def _delete_recurrence(self, params, body):
        self._require_planning().recurrences.delete(params["id"])
        return 200, {"result": "deleted"}

    # --- inbox / quick capture (M20) --------------------------------------------

    def _get_inbox(self, params, body):
        return 200, {"items": self._require_planning().inbox.list()}

    def _post_inbox(self, params, body):
        record = self._require_planning().inbox.add(
            schemas.require_string(body, "text"), self._app.current_time()
        )
        return 201, record

    def _post_inbox_convert(self, params, body):
        planning = self._require_planning()
        item = planning.inbox.get(params["id"])
        target = schemas.require_string(body, "to").lower()
        title = schemas.optional_string(body, "title") or item["text"]
        now = self._app.current_time()
        if target == "goal":
            goal = self._app.add_goal(self._owner(body), title, "")
            created = serialization.serialize_goal(goal)
            reference = f"goal:{goal.goal_id}"
        elif target == "project":
            project = self._app.add_project(self._owner(body), title, "")
            created = serialization.serialize_project(
                project, self._app.get_project_progress(project.project_id)
            )
            reference = f"project:{project.project_id}"
        elif target == "event":
            recommendation, event_id = self._app.propose_user_event(
                self._owner(body),
                title,
                suggested_time=schemas.optional_datetime(
                    body, "suggested_time"
                ),
                priority=schemas.optional_number(body, "priority"),
            )
            created = serialization.serialize_proposed(
                recommendation, event_id
            )
            reference = "event:" + (
                str(event_id) if event_id is not None
                else str(recommendation.recommendation_id)
            )
            self._store_metadata(
                reference.removeprefix("event:"),
                schemas.optional_object(body, "metadata"),
            )
        else:
            raise ApiError(
                400, "Field 'to' must be 'goal', 'project' or 'event'"
            )
        record = planning.inbox.mark_converted(params["id"], reference, now)
        return 200, {"item": record, "created": created}

    def _post_inbox_archive(self, params, body):
        record = self._require_planning().inbox.archive(
            params["id"], self._app.current_time()
        )
        return 200, record

    def _delete_inbox(self, params, body):
        self._require_planning().inbox.delete(params["id"])
        return 200, {"result": "deleted"}

    # --- assistant (M20: proposals and explanations ONLY) ----------------------

    def _get_assistant_status(self, params, body):
        return 200, {
            "provider": self._assistant_provider,
            "available": self._assistant is not None,
            "fallback": "heuristic",
            "reason": self._assistant_reason,
        }

    # --- intelligence layer: setup + settings (transport concern) ----------

    def _require_ai_dir(self):
        if self._ai_dir is None:
            raise ApiError(503, "AI settings are not composed")
        return self._ai_dir

    def _get_assistant_setup(self, params, body):
        """Hardware, model recommendations and Ollama state — the one
        call behind "Choose your PAIOS Intelligence Mode"."""
        return 200, ollama_support.setup_report()

    def _get_assistant_ollama(self, params, body):
        return 200, ollama_support.status()

    def _post_assistant_ollama_pull(self, params, body):
        model = schemas.require_string(body, "model")
        return 200, ollama_support.start_pull(model)

    def _post_assistant_ollama_remove(self, params, body):
        model = schemas.require_string(body, "model")
        return 200, ollama_support.remove_model(model)

    def _get_assistant_config(self, params, body):
        ai_dir = self._require_ai_dir()
        stored = ai_settings.load(ai_dir)
        return 200, {
            "provider": self._assistant_provider,
            "model": stored.get("model"),
            "providers": list(assistant_support.PROVIDERS),
            "stored_keys": {
                provider: ai_settings.has_stored_key(ai_dir, provider)
                for provider in ai_settings.KEY_VARIABLES
            },
            "env_override": bool(os.environ.get("PAIOS_AI_PROVIDER")),
            "available": self._assistant is not None,
            "reason": self._assistant_reason,
        }

    def _put_assistant_config(self, params, body):
        """Persist provider/model (and optionally a cloud API key),
        then recompose the assistant live — no restart needed. The
        heuristic fallback is untouched by any outcome here."""
        ai_dir = self._require_ai_dir()
        provider = schemas.require_string(body, "provider").strip().lower()
        if provider not in assistant_support.PROVIDERS:
            raise ApiError(
                400,
                "Field 'provider' must be one of: "
                + ", ".join(assistant_support.PROVIDERS),
            )
        model = schemas.optional_string(body, "model")
        api_key = schemas.optional_string(body, "api_key")
        key_warning = None
        if api_key:
            if provider not in ai_settings.KEY_VARIABLES:
                raise ApiError(
                    400, f"Provider {provider!r} takes no API key"
                )
            if not ai_settings.store_api_key(ai_dir, provider, api_key):
                key_warning = (
                    "Secure key storage is unavailable on this platform"
                    " — set the "
                    + ai_settings.KEY_VARIABLES[provider]
                    + " environment variable instead. The key was NOT"
                    " stored."
                )
        ai_settings.save(ai_dir, {"provider": provider, "model": model})
        stored_key = ai_settings.api_key_for(ai_dir, provider)
        (
            self._assistant_provider,
            self._assistant,
            self._assistant_reason,
        ) = assistant_support.compose_assistant(
            provider, model, api_key=stored_key
        )
        payload = {
            "provider": self._assistant_provider,
            "available": self._assistant is not None,
            "fallback": "heuristic",
            "reason": self._assistant_reason,
        }
        if key_warning:
            payload["warning"] = key_warning
        return 200, payload

    def _post_assistant_test(self, params, body):
        """One tiny round trip proving the configured provider answers.
        Deterministic reply when no provider is active."""
        if self._assistant is None:
            return 200, {
                "source": "heuristic",
                "ok": True,
                "answer": (
                    "No AI provider is active — PAIOS is answering"
                    " deterministically, which always works."
                ),
                "reason": self._assistant_reason,
            }
        try:
            result = self._assistant.answer_question(
                "Reply with one short sentence confirming the PAIOS"
                " assistant is reachable."
            )
        except assistant_support.FALLBACK_ERRORS as error:
            return 200, {
                "source": "llm",
                "ok": False,
                "answer": f"The provider did not answer: {error}",
            }
        return 200, {
            "source": "llm",
            "ok": True,
            "adapter": result.adapter,
            "answer": result.answer,
        }

    # --- intelligence layer: daily-rhythm workflows ------------------------
    # Read-only observations in both paths (LLM or deterministic); the
    # Scheduler and Decision Engine remain the only authorities.

    def _today(self) -> str:
        return self._app.current_time().isoformat()[:10]

    def _plan_lines(self) -> list[str]:
        entries = assistant_support.deterministic_day_reasons(
            self._app, self._require_planning()
        )
        return [
            f"{entry['planned_start'][11:16]} {entry['title']}"
            f" ({entry['reason']})"
            for entry in entries
        ]

    def _post_assistant_morning_plan(self, params, body):
        check_in = {
            "sleep_hours": schemas.optional_number(body, "sleep_hours"),
            "mood": schemas.optional_string(body, "mood"),
            "energy": schemas.optional_string(body, "energy"),
            "notes": schemas.optional_string(body, "notes"),
        }
        fallback = assistant_support.heuristic_morning_payload(
            self._app, self._require_planning(), check_in, self._today()
        )
        if self._assistant is None:
            return 200, fallback
        try:
            check_in_text = "; ".join(
                f"{name}: {value}"
                for name, value in check_in.items()
                if value is not None
            )
            result = self._assistant.morning_plan(
                check_in_text,
                self._plan_lines(),
                snapshot=self._app.snapshot(),
                goals=self._app.list_goals(),
            )
        except assistant_support.FALLBACK_ERRORS:
            return 200, fallback
        return 200, {
            "source": "llm",
            "adapter": result.adapter,
            "answer": result.answer,
            "bullets": list(result.bullets),
            "timeline": fallback["timeline"],
            "priorities": fallback["priorities"],
            "risks": fallback["risks"],
            "confidence": result.confidence,
        }

    def _post_assistant_evening_review(self, params, body):
        check_in = {
            "notes": schemas.optional_string(body, "notes"),
            "productivity": schemas.optional_number(body, "productivity"),
        }
        fallback = assistant_support.heuristic_evening_payload(
            self._app, check_in, self._today()
        )
        if self._assistant is None:
            return 200, fallback
        try:
            today_lines = [
                f"completed: {title}" for title in fallback["completed"]
            ] + [f"planned tomorrow: {t}" for t in fallback["tomorrow"]]
            check_in_text = "; ".join(
                f"{name}: {value}"
                for name, value in check_in.items()
                if value is not None
            )
            result = self._assistant.evening_review(
                check_in_text,
                today_lines,
                snapshot=self._app.snapshot(),
            )
        except assistant_support.FALLBACK_ERRORS:
            return 200, fallback
        return 200, {
            "source": "llm",
            "adapter": result.adapter,
            "answer": result.answer,
            "bullets": list(result.bullets),
            "completed": fallback["completed"],
            "improvements": fallback["improvements"],
            "tomorrow": fallback["tomorrow"],
            "confidence": result.confidence,
        }

    def _post_assistant_weekly_review(self, params, body):
        today = self._app.current_time()
        week_days = [
            (today - timedelta(days=offset)).isoformat()[:10]
            for offset in range(6, -1, -1)
        ]
        fallback = assistant_support.heuristic_weekly_payload(
            self._app, week_days
        )
        if self._assistant is None:
            return 200, fallback
        try:
            result = self._assistant.summarize_week(
                events=self._app.list_events(),
                goals=self._app.list_goals(),
                projects=self._app.list_projects(),
            )
        except assistant_support.FALLBACK_ERRORS:
            return 200, fallback
        return 200, {
            "source": "llm",
            "adapter": result.adapter,
            "answer": result.answer,
            "bullets": list(result.bullets),
            "per_day": fallback["per_day"],
            "confidence": result.confidence,
        }

    # --- mobile companion (paired devices only) -----------------------------

    def _require_mobile(self) -> "mobile_support.PairingService":
        if self._mobile is None:
            raise ApiError(503, "Mobile services are not composed")
        return self._mobile

    def _require_loopback(self) -> None:
        if not mobile_support.is_loopback(self._request_client):
            raise ApiError(
                403, "Pairing administration is desktop-only"
            )

    def _require_device(self) -> str:
        token = mobile_support.bearer_token(self._request_headers)
        device_id = self._require_mobile().authenticate(
            token, self._app.current_time()
        )
        if device_id is None:
            raise ApiError(
                401,
                "Not paired — pair this device from PAIOS on the desktop",
            )
        return device_id

    def _post_mobile_pairing_start(self, params, body):
        self._require_loopback()
        return 200, self._require_mobile().begin(self._app.current_time())

    def _get_mobile_devices(self, params, body):
        self._require_loopback()
        return 200, {"devices": self._require_mobile().devices()}

    def _delete_mobile_device(self, params, body):
        self._require_loopback()
        if not self._require_mobile().revoke(params["id"]):
            raise ApiError(404, f"Unknown device: {params['id']}")
        return 200, {"result": "revoked"}

    def _post_mobile_pair(self, params, body):
        try:
            device_id, token = self._require_mobile().complete(
                schemas.require_string(body, "code"),
                schemas.optional_string(body, "device_name") or "",
                self._app.current_time(),
            )
        except mobile_support.MobileAuthError as error:
            raise ApiError(401, str(error)) from error
        return 201, {"device_id": device_id, "token": token}

    def _post_mobile_auth(self, params, body):
        token = schemas.require_string(body, "token")
        device_id = self._require_mobile().authenticate(
            token, self._app.current_time()
        )
        if device_id is None:
            raise ApiError(401, "Invalid or revoked token")
        return 200, {"device_id": device_id, "valid": True}

    def _get_mobile_timeline(self, params, body):
        self._require_device()
        entries = assistant_support.deterministic_day_reasons(
            self._app, self._require_planning()
        )
        return 200, {
            "server_time": self._app.current_time().isoformat(),
            "day": self._today(),
            "entries": entries,
        }

    def _get_mobile_tasks(self, params, body):
        self._require_device()
        return 200, {
            "server_time": self._app.current_time().isoformat(),
            "events": [
                serialization.serialize_event(event)
                for event in self._app.list_events()
            ],
        }

    def _post_mobile_tasks(self, params, body):
        self._require_device()
        return self._post_events(params, body)

    def _get_mobile_logs(self, params, body):
        self._require_device()
        return 200, {
            "entries": self._require_planning().logs.list(
                day=params.get("day")
            )
        }

    def _post_mobile_logs(self, params, body):
        self._require_device()
        explicit_at = schemas.optional_datetime(body, "at")
        record = self._require_planning().logs.add(
            schemas.optional_string(body, "kind") or "journal",
            schemas.require_string(body, "text"),
            explicit_at
            if explicit_at is not None
            else self._app.current_time(),
            client_id=schemas.optional_string(body, "client_id"),
            extra=schemas.optional_object(body, "extra"),
        )
        return 201, record

    def _get_mobile_study(self, params, body):
        self._require_device()
        return 200, {
            "knowledge": [
                serialization.serialize_knowledge(item)
                for item in self._app.list_knowledge()
            ],
            "study_logs": self._require_planning().logs.list(kind="study"),
        }

    def _post_mobile_assistant_query(self, params, body):
        self._require_device()
        question = schemas.require_string(body, "text")
        if self._assistant is None:
            return 200, {
                "source": "heuristic",
                "answer": (
                    "No AI provider is configured on the desktop."
                    " PAIOS still plans deterministically — configure"
                    " an intelligence mode in desktop Settings for"
                    " conversational answers."
                ),
                "bullets": [],
                "confidence": None,
            }
        try:
            result = self._assistant.answer_question(
                question,
                snapshot=self._app.snapshot(),
                goals=self._app.list_goals(),
                projects=self._app.list_projects(),
                events=self._app.list_events(),
            )
        except assistant_support.FALLBACK_ERRORS as error:
            return 200, {
                "source": "heuristic",
                "answer": f"The AI provider did not answer ({error})."
                " Try again, or check desktop Settings.",
                "bullets": [],
                "confidence": None,
            }
        return 200, {
            "source": "llm",
            "adapter": result.adapter,
            "answer": result.answer,
            "bullets": list(result.bullets),
            "confidence": result.confidence,
        }

    def _post_assistant_plan(self, params, body):
        text = schemas.require_string(body, "text")
        goals = tuple(goal.name for goal in self._app.list_goals())
        projects = tuple(
            project.name for project in self._app.list_projects()
        )
        events = tuple(
            event.description
            for event in self._app.list_events()
            if getattr(event.status, "value", str(event.status)) != "Archived"
        )[:200]
        if self._assistant is not None:
            try:
                proposal = self._assistant.classify_captures(
                    text,
                    existing_goals=goals,
                    existing_projects=projects,
                    existing_events=events,
                )
                return 200, assistant_support.proposal_payload(proposal)
            except assistant_support.FALLBACK_ERRORS:
                pass  # deterministic path answers instead
        return 200, assistant_support.heuristic_proposal_payload(
            text, goals, projects, events
        )

    def _post_assistant_explain_day(self, params, body):
        planning = self._require_planning()
        entries = assistant_support.deterministic_day_reasons(
            self._app, planning
        )
        payload = {"source": "deterministic", "entries": entries}
        if self._assistant is not None and entries:
            plan_lines = [
                f"{entry['planned_start']} {entry['title']} "
                f"({entry['duration_minutes']}m)"
                for entry in entries
            ]
            facts = [
                f"{entry['title']}: {entry['reason']}" for entry in entries
            ]
            try:
                result = self._assistant.explain_day_plan(plan_lines, facts)
                payload = {
                    "source": "llm",
                    "answer": result.answer,
                    "bullets": list(result.bullets),
                    "entries": entries,
                }
            except assistant_support.FALLBACK_ERRORS:
                pass
        return 200, payload

    # --- backups (M20: wraps the existing system BackupManager) ----------------

    def _get_backups(self, params, body):
        archives = self._require_backups().list_backups()
        return 200, {
            "backups": [
                {"name": archive.name, "size_bytes": archive.stat().st_size}
                for archive in archives
            ]
        }

    def _post_backups(self, params, body):
        archive = self._require_backups().create(
            now=self._app.current_time()
        )
        return 201, {"name": archive.name}

    def _post_backups_restore(self, params, body):
        restored = self._require_backups().restore(
            schemas.require_string(body, "archive")
        )
        return 200, {
            "restored": restored,
            "note": (
                "Restored files load at the next application start; "
                "restart PAIOS to adopt them."
            ),
        }

    # --- M20 shared helpers -----------------------------------------------------

    def _store_metadata(self, key: str, metadata) -> None:
        if metadata and self._planning is not None:
            self._planning.metadata.set(
                key, metadata, self._app.current_time()
            )

    def _optional_project(self, body):
        token = schemas.optional_string(body, "project_id")
        return ProjectId(token) if token is not None else None

    def _expand_due_recurrences(self) -> int:
        """Called from POST /tick when planning is composed: each due
        rule becomes one proposed intent; the rule then advances. The
        Scheduler decides everything about the resulting Event."""
        if self._planning is None:
            return 0
        now = self._app.current_time()
        owner = self._owner({})
        expanded = 0
        for rule in self._planning.due_recurrences(now):
            intent, default_metadata, next_run = (
                self._planning.expand_recurrence(rule, owner, now)
            )
            recommendation, event_id = self._app.propose_user_event(
                intent.user_id,
                intent.title,
                suggested_time=intent.suggested_time,
            )
            self._store_metadata(
                str(event_id) if event_id is not None
                else str(recommendation.recommendation_id),
                default_metadata or None,
            )
            self._planning.recurrences.set_next_run(rule["id"], next_run)
            expanded += 1
        return expanded

    # --- goals -----------------------------------------------------------

    def _get_goals(self, params, body):
        return 200, {
            "goals": [
                serialization.serialize_goal(goal)
                for goal in self._app.list_goals()
            ]
        }

    def _post_goals(self, params, body):
        goal = self._app.add_goal(
            self._owner(body),
            schemas.require_string(body, "name"),
            schemas.optional_string(body, "description") or "",
        )
        return 201, serialization.serialize_goal(goal)

    def _post_goal_complete(self, params, body):
        goal = self._app.complete_goal(GoalId(params["id"]))
        return 200, serialization.serialize_goal(goal)

    def _post_goal_pause(self, params, body):
        goal = self._app.pause_goal(GoalId(params["id"]))
        return 200, serialization.serialize_goal(goal)

    def _post_goal_resume(self, params, body):
        goal = self._app.resume_goal(GoalId(params["id"]))
        return 200, serialization.serialize_goal(goal)

    # --- projects --------------------------------------------------------

    def _get_projects(self, params, body):
        return 200, {
            "projects": [
                serialization.serialize_project(
                    project,
                    self._app.get_project_progress(project.project_id),
                )
                for project in self._app.list_projects()
            ]
        }

    def _post_projects(self, params, body):
        project = self._app.add_project(
            self._owner(body),
            schemas.require_string(body, "name"),
            schemas.optional_string(body, "description") or "",
        )
        return 201, serialization.serialize_project(
            project, self._app.get_project_progress(project.project_id)
        )

    def _post_project_progress(self, params, body):
        project_id = ProjectId(params["id"])
        self._app.update_project_progress(
            project_id,
            schemas.require_number(body, "completion_percentage"),
        )
        return 200, serialization.serialize_project(
            self._app.get_project(project_id),
            self._app.get_project_progress(project_id),
        )

    # --- resources -------------------------------------------------------

    def _get_resources(self, params, body):
        return 200, {
            "resources": [
                serialization.serialize_resource(resource)
                for resource in self._app.list_resources()
            ]
        }

    def _post_resources(self, params, body):
        resource = self._app.add_resource(
            self._owner(body),
            schemas.parse_enum(
                ResourceType, schemas.require_string(body, "type"), "type"
            ),
            schemas.require_number(body, "current_value"),
            schemas.require_string(body, "unit"),
            schemas.optional_bool(body, "negative_allowed"),
        )
        return 201, serialization.serialize_resource(resource)

    def _post_resource_consume(self, params, body):
        resource = self._app.consume_resource(
            ResourceId(params["id"]), schemas.require_number(body, "amount")
        )
        return 200, serialization.serialize_resource(resource)

    def _post_resource_produce(self, params, body):
        resource = self._app.produce_resource(
            ResourceId(params["id"]), schemas.require_number(body, "amount")
        )
        return 200, serialization.serialize_resource(resource)

    # --- knowledge -------------------------------------------------------

    def _get_knowledge(self, params, body):
        return 200, {
            "knowledge": [
                serialization.serialize_knowledge(item)
                for item in self._app.list_knowledge()
            ]
        }

    def _post_knowledge(self, params, body):
        project_token = schemas.optional_string(body, "project_id")
        knowledge = self._app.add_knowledge(
            self._owner(body),
            schemas.require_string(body, "domain"),
            schemas.require_string(body, "topic"),
            schemas.require_string(body, "concept"),
            project_id=(
                ProjectId(project_token) if project_token is not None else None
            ),
            difficulty=schemas.optional_string(body, "difficulty"),
            confidence=schemas.optional_number(body, "confidence") or 0.0,
            source=schemas.optional_string(body, "source"),
        )
        return 201, serialization.serialize_knowledge(knowledge)

    # --- reflections -----------------------------------------------------

    def _get_reflections(self, params, body):
        return 200, {
            "reflections": [
                serialization.serialize_reflection(reflection)
                for reflection in self._app.list_reflections()
            ]
        }

    def _post_reflections(self, params, body):
        reflection = self._app.add_reflection(
            EventId(schemas.require_string(body, "event_id")),
            facts=schemas.optional_string(body, "facts"),
            interpretation=schemas.optional_string(body, "interpretation"),
            root_cause=schemas.optional_string(body, "root_cause"),
            lesson_learned=schemas.optional_string(body, "lesson_learned"),
            improvement=schemas.optional_string(body, "improvement"),
            confidence=schemas.optional_number(body, "confidence"),
        )
        return 201, serialization.serialize_reflection(reflection)

    # --- disturbers (Milestone 13: the GUI's Report Disturbance) ----------

    def _post_disturbers(self, params, body):
        disturber = self._app.report_disturber(
            self._owner(body),
            schemas.parse_enum(
                DisturberType, schemas.require_string(body, "type"), "type"
            ),
            schemas.require_string(body, "description"),
            schemas.parse_enum(
                DisturberSeverity,
                schemas.require_string(body, "severity"),
                "severity",
            ),
        )
        return 201, serialization.serialize_disturber(disturber)

    # --- contexts --------------------------------------------------------

    def _get_contexts(self, params, body):
        return 200, {
            "contexts": [
                serialization.serialize_context(context)
                for context in self._app.list_contexts()
            ]
        }

    # --- dashboard -------------------------------------------------------

    def _get_dashboard(self, params, body):
        return 200, serialization.dashboard_payload(self._app)

    # --- input resolution (the CLI convention) ----------------------------

    def _owner(self, body) -> UserId:
        explicit = schemas.optional_string(body, "user_id")
        if explicit is not None:
            return UserId(explicit)
        users = self._app.list_users()
        if users:
            return users[0].user_id
        return UserId(DEFAULT_USER_ID)


def _match(pattern: tuple[str, ...], segments: tuple[str, ...]):
    """Match /a/{id}/b patterns; returns captured params or None."""
    if len(pattern) != len(segments):
        return None
    params: dict[str, str] = {}
    for expected, actual in zip(pattern, segments):
        if expected.startswith("{") and expected.endswith("}"):
            params[expected[1:-1]] = actual
        elif expected != actual:
            return None
    return params


_ROUTES: tuple[tuple[str, tuple[str, ...], object], ...] = (
    ("GET", ("status",), ApiRouter._get_status),
    ("GET", ("snapshot",), ApiRouter._get_snapshot),
    ("POST", ("tick",), ApiRouter._post_tick),
    ("GET", ("recommendations",), ApiRouter._get_recommendations),
    (
        "POST",
        ("recommendations", "{id}", "accept"),
        ApiRouter._post_recommendation_accept,
    ),
    (
        "POST",
        ("recommendations", "{id}", "reject"),
        ApiRouter._post_recommendation_reject,
    ),
    ("GET", ("events",), ApiRouter._get_events),
    ("POST", ("events",), ApiRouter._post_events),
    ("GET", ("events", "{id}"), ApiRouter._get_event),
    ("PUT", ("events", "{id}"), ApiRouter._put_event),
    (
        "POST",
        ("events", "{id}", "duplicate"),
        ApiRouter._post_event_duplicate,
    ),
    ("GET", ("events", "{id}", "metadata"), ApiRouter._get_event_metadata),
    ("PUT", ("events", "{id}", "metadata"), ApiRouter._put_event_metadata),
    ("POST", ("events", "{id}", "start"), ApiRouter._post_event_start),
    ("POST", ("events", "{id}", "pause"), ApiRouter._post_event_pause),
    ("POST", ("events", "{id}", "resume"), ApiRouter._post_event_resume),
    ("POST", ("events", "{id}", "complete"), ApiRouter._post_event_complete),
    ("POST", ("events", "{id}", "cancel"), ApiRouter._post_event_cancel),
    ("POST", ("events", "{id}", "archive"), ApiRouter._post_event_archive),
    ("GET", ("goals",), ApiRouter._get_goals),
    ("POST", ("goals",), ApiRouter._post_goals),
    ("POST", ("goals", "{id}", "complete"), ApiRouter._post_goal_complete),
    ("POST", ("goals", "{id}", "pause"), ApiRouter._post_goal_pause),
    ("POST", ("goals", "{id}", "resume"), ApiRouter._post_goal_resume),
    ("GET", ("projects",), ApiRouter._get_projects),
    ("POST", ("projects",), ApiRouter._post_projects),
    (
        "POST",
        ("projects", "{id}", "progress"),
        ApiRouter._post_project_progress,
    ),
    ("GET", ("resources",), ApiRouter._get_resources),
    ("POST", ("resources",), ApiRouter._post_resources),
    (
        "POST",
        ("resources", "{id}", "consume"),
        ApiRouter._post_resource_consume,
    ),
    (
        "POST",
        ("resources", "{id}", "produce"),
        ApiRouter._post_resource_produce,
    ),
    ("GET", ("knowledge",), ApiRouter._get_knowledge),
    ("POST", ("knowledge",), ApiRouter._post_knowledge),
    ("GET", ("reflections",), ApiRouter._get_reflections),
    ("POST", ("reflections",), ApiRouter._post_reflections),
    ("POST", ("disturbers",), ApiRouter._post_disturbers),
    ("GET", ("contexts",), ApiRouter._get_contexts),
    ("GET", ("dashboard",), ApiRouter._get_dashboard),
    # --- Milestone 20 additive routes (approved 2026-07-22) ---------------
    ("GET", ("plan",), ApiRouter._get_plan),
    ("GET", ("templates",), ApiRouter._get_templates),
    ("POST", ("templates",), ApiRouter._post_templates),
    ("DELETE", ("templates", "{id}"), ApiRouter._delete_template),
    (
        "POST",
        ("templates", "{id}", "instantiate"),
        ApiRouter._post_template_instantiate,
    ),
    ("GET", ("recurrences",), ApiRouter._get_recurrences),
    ("POST", ("recurrences",), ApiRouter._post_recurrences),
    ("DELETE", ("recurrences", "{id}"), ApiRouter._delete_recurrence),
    ("GET", ("inbox",), ApiRouter._get_inbox),
    ("POST", ("inbox",), ApiRouter._post_inbox),
    ("POST", ("inbox", "{id}", "convert"), ApiRouter._post_inbox_convert),
    ("POST", ("inbox", "{id}", "archive"), ApiRouter._post_inbox_archive),
    ("DELETE", ("inbox", "{id}"), ApiRouter._delete_inbox),
    ("GET", ("assistant", "status"), ApiRouter._get_assistant_status),
    ("POST", ("assistant", "plan"), ApiRouter._post_assistant_plan),
    (
        "POST",
        ("assistant", "explain-day"),
        ApiRouter._post_assistant_explain_day,
    ),
    # --- intelligence layer: setup, settings, daily rhythm -----------------
    ("GET", ("assistant", "setup"), ApiRouter._get_assistant_setup),
    ("GET", ("assistant", "ollama"), ApiRouter._get_assistant_ollama),
    (
        "POST",
        ("assistant", "ollama", "pull"),
        ApiRouter._post_assistant_ollama_pull,
    ),
    (
        "POST",
        ("assistant", "ollama", "remove"),
        ApiRouter._post_assistant_ollama_remove,
    ),
    ("GET", ("assistant", "config"), ApiRouter._get_assistant_config),
    ("PUT", ("assistant", "config"), ApiRouter._put_assistant_config),
    ("POST", ("assistant", "test"), ApiRouter._post_assistant_test),
    (
        "POST",
        ("assistant", "morning-plan"),
        ApiRouter._post_assistant_morning_plan,
    ),
    (
        "POST",
        ("assistant", "evening-review"),
        ApiRouter._post_assistant_evening_review,
    ),
    (
        "POST",
        ("assistant", "weekly-review"),
        ApiRouter._post_assistant_weekly_review,
    ),
    # --- mobile companion (paired devices; pairing admin loopback-only) ----
    (
        "POST",
        ("mobile", "pairing", "start"),
        ApiRouter._post_mobile_pairing_start,
    ),
    (
        "GET",
        ("mobile", "pairing", "devices"),
        ApiRouter._get_mobile_devices,
    ),
    (
        "DELETE",
        ("mobile", "pairing", "devices", "{id}"),
        ApiRouter._delete_mobile_device,
    ),
    ("POST", ("mobile", "pair"), ApiRouter._post_mobile_pair),
    ("POST", ("mobile", "auth"), ApiRouter._post_mobile_auth),
    ("GET", ("mobile", "timeline"), ApiRouter._get_mobile_timeline),
    ("GET", ("mobile", "tasks"), ApiRouter._get_mobile_tasks),
    ("POST", ("mobile", "tasks"), ApiRouter._post_mobile_tasks),
    ("GET", ("mobile", "logs"), ApiRouter._get_mobile_logs),
    ("GET", ("mobile", "logs", "{day}"), ApiRouter._get_mobile_logs),
    ("POST", ("mobile", "logs"), ApiRouter._post_mobile_logs),
    ("GET", ("mobile", "study"), ApiRouter._get_mobile_study),
    (
        "POST",
        ("mobile", "assistant", "query"),
        ApiRouter._post_mobile_assistant_query,
    ),
    ("GET", ("backups",), ApiRouter._get_backups),
    ("POST", ("backups",), ApiRouter._post_backups),
    ("POST", ("backups", "restore"), ApiRouter._post_backups_restore),
)
