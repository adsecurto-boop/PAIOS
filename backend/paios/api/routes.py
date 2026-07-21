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
from paios.api import schemas, serialization
from paios.api.errors import ApiError, translate

#: Fallback owner when the store holds no users (the CLI convention).
DEFAULT_USER_ID = "user_001"


class ApiRouter:
    """Pure request core: (method, path, body) -> (status, payload).

    No sockets, no streams — the HTTP server binds this to the wire;
    tests call it directly.
    """

    def __init__(self, application: Application) -> None:
        self._app = application

    # --- dispatch --------------------------------------------------------

    def handle(self, method: str, path: str, body=None) -> tuple[int, dict]:
        try:
            return self._dispatch(method.upper(), path, body)
        except Exception as error:  # translated, never propagated
            return translate(error)

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
        return 200, serialization.serialize_decision_result(self._app.tick())

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
    ("GET", ("events", "{id}"), ApiRouter._get_event),
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
)
