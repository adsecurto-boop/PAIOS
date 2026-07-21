"""The REST client: the GUI's single doorway into PAIOS.

Pure stdlib (urllib) — no paios imports, no third-party HTTP library.
One method per REST endpoint the GUI uses; every GUI action maps to
exactly one method here, and every method issues exactly one request.

Failures become one of two exceptions:

- ApiUnreachable  — connection refused / reset / timed out (server down
  or network gone); the window shows the offline banner and keeps
  retrying on its poll timer.
- ApiResponseError — the server answered with an error payload
  (validation failure, unknown entity, conflict); carries the HTTP
  status and the API's ``{"error": {"type", "message"}}`` fields.
"""

import json
import urllib.error
import urllib.request


class ApiUnreachable(Exception):
    """The server could not be reached at all."""


class ApiResponseError(Exception):
    """The server answered with an HTTP error status."""

    def __init__(self, status: int, error_type: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.error_type = error_type


class ApiClient:
    def __init__(self, base_url: str, timeout: float = 2.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    @property
    def base_url(self) -> str:
        return self._base_url

    # --- transport -------------------------------------------------------

    def _request(self, method: str, path: str, body: dict | None = None):
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            self._base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._timeout
            ) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise _response_error(error) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise ApiUnreachable(str(error)) from error

    # --- reads (polling) -------------------------------------------------

    def get_status(self) -> dict:
        return self._request("GET", "/status")

    def get_dashboard(self) -> dict:
        return self._request("GET", "/dashboard")

    def get_goals(self) -> list[dict]:
        return self._request("GET", "/goals")["goals"]

    def get_projects(self) -> list[dict]:
        return self._request("GET", "/projects")["projects"]

    def get_events(self) -> list[dict]:
        return self._request("GET", "/events")["events"]

    def get_resources(self) -> list[dict]:
        return self._request("GET", "/resources")["resources"]

    def get_knowledge(self) -> list[dict]:
        return self._request("GET", "/knowledge")["knowledge"]

    def get_reflections(self) -> list[dict]:
        return self._request("GET", "/reflections")["reflections"]

    def get_recommendations(self) -> list[dict]:
        return self._request("GET", "/recommendations")["recommendations"]

    # --- actions (one endpoint each; the mission's action list) ----------

    def accept_recommendation(self, recommendation_id: str) -> dict:
        return self._request(
            "POST", f"/recommendations/{recommendation_id}/accept", {}
        )

    def reject_recommendation(
        self, recommendation_id: str, reason: str | None = None
    ) -> dict:
        body = {} if reason is None else {"reason": reason}
        return self._request(
            "POST", f"/recommendations/{recommendation_id}/reject", body
        )

    def start_event(self, event_id: str) -> dict:
        return self._request("POST", f"/events/{event_id}/start", {})

    def pause_event(self, event_id: str) -> dict:
        return self._request("POST", f"/events/{event_id}/pause", {})

    def resume_event(self, event_id: str) -> dict:
        return self._request("POST", f"/events/{event_id}/resume", {})

    def complete_event(
        self, event_id: str, actual_outcome: str | None = None
    ) -> dict:
        body = {} if actual_outcome is None else {
            "actual_outcome": actual_outcome
        }
        return self._request("POST", f"/events/{event_id}/complete", body)

    def cancel_event(self, event_id: str, reason: str | None = None) -> dict:
        body = {} if reason is None else {"reason": reason}
        return self._request("POST", f"/events/{event_id}/cancel", body)

    def create_goal(self, name: str, description: str = "") -> dict:
        return self._request(
            "POST", "/goals", {"name": name, "description": description}
        )

    def create_project(self, name: str, description: str = "") -> dict:
        return self._request(
            "POST", "/projects", {"name": name, "description": description}
        )

    def update_progress(
        self, project_id: str, completion_percentage: float
    ) -> dict:
        return self._request(
            "POST",
            f"/projects/{project_id}/progress",
            {"completion_percentage": completion_percentage},
        )

    def create_reflection(self, event_id: str, **fields) -> dict:
        body = {"event_id": event_id}
        body.update(
            {key: value for key, value in fields.items() if value is not None}
        )
        return self._request("POST", "/reflections", body)

    def report_disturber(
        self, type: str, severity: str, description: str
    ) -> dict:
        return self._request(
            "POST",
            "/disturbers",
            {"type": type, "severity": severity, "description": description},
        )


def _response_error(error: urllib.error.HTTPError) -> ApiResponseError:
    """Decode the API's JSON error payload; degrade to the raw reason."""
    try:
        payload = json.loads(error.read().decode("utf-8"))
        detail = payload["error"]
        return ApiResponseError(
            error.code, detail["type"], detail["message"]
        )
    except Exception:
        return ApiResponseError(error.code, "HttpError", str(error.reason))
