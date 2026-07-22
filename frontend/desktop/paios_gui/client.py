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

    # --- events: user-authored intents (M20) -------------------------------
    # Creation/edit/duplicate reply with the proposed shape
    # {"recommendation", "event_id", "materialized"} — edit is
    # cancel+recreate on the server, so the returned event_id is NEW.

    def create_event(self, title: str, **fields) -> dict:
        body = {"title": title}
        body.update(
            {key: value for key, value in fields.items() if value is not None}
        )
        return self._request("POST", "/events", body)

    def edit_event(self, event_id: str, title: str, **fields) -> dict:
        body = {"title": title}
        body.update(
            {key: value for key, value in fields.items() if value is not None}
        )
        return self._request("PUT", f"/events/{event_id}", body)

    def duplicate_event(
        self, event_id: str, suggested_time: str | None = None
    ) -> dict:
        body = {} if suggested_time is None else {
            "suggested_time": suggested_time
        }
        return self._request("POST", f"/events/{event_id}/duplicate", body)

    def archive_event(self, event_id: str) -> dict:
        return self._request("POST", f"/events/{event_id}/archive", {})

    def get_event_metadata(self, event_id: str) -> dict:
        return self._request("GET", f"/events/{event_id}/metadata")

    def set_event_metadata(self, event_id: str, metadata: dict) -> dict:
        return self._request("PUT", f"/events/{event_id}/metadata", metadata)

    # --- plan / timeline (M20) ---------------------------------------------

    def get_plan(self) -> dict:
        return self._request("GET", "/plan")

    # --- templates (M20) -----------------------------------------------------

    def list_templates(self) -> list[dict]:
        return self._request("GET", "/templates")["templates"]

    def create_template(
        self,
        name: str,
        title: str,
        category: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        body = {"name": name, "title": title}
        if category is not None:
            body["category"] = category
        if metadata is not None:
            body["metadata"] = metadata
        return self._request("POST", "/templates", body)

    def delete_template(self, template_id: str) -> dict:
        return self._request("DELETE", f"/templates/{template_id}")

    def instantiate_template(
        self,
        template_id: str,
        suggested_time: str | None = None,
        priority: float | None = None,
    ) -> dict:
        body = {}
        if suggested_time is not None:
            body["suggested_time"] = suggested_time
        if priority is not None:
            body["priority"] = priority
        return self._request(
            "POST", f"/templates/{template_id}/instantiate", body
        )

    # --- recurrences (M20) ----------------------------------------------------

    def list_recurrences(self) -> list[dict]:
        return self._request("GET", "/recurrences")["recurrences"]

    def create_recurrence(
        self,
        title: str,
        time_of_day: str,
        days: list[str],
        first_run: str | None = None,
        category: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        body = {"title": title, "time_of_day": time_of_day, "days": days}
        if first_run is not None:
            body["first_run"] = first_run
        if category is not None:
            body["category"] = category
        if metadata is not None:
            body["metadata"] = metadata
        return self._request("POST", "/recurrences", body)

    def delete_recurrence(self, recurrence_id: str) -> dict:
        return self._request("DELETE", f"/recurrences/{recurrence_id}")

    # --- inbox / quick capture (M20) --------------------------------------------

    def list_inbox(self) -> list[dict]:
        return self._request("GET", "/inbox")["items"]

    def add_inbox(self, text: str) -> dict:
        return self._request("POST", "/inbox", {"text": text})

    def convert_inbox(self, item_id: str, to: str, **fields) -> dict:
        body = {"to": to}
        body.update(
            {key: value for key, value in fields.items() if value is not None}
        )
        return self._request("POST", f"/inbox/{item_id}/convert", body)

    def archive_inbox(self, item_id: str) -> dict:
        return self._request("POST", f"/inbox/{item_id}/archive", {})

    def delete_inbox(self, item_id: str) -> dict:
        return self._request("DELETE", f"/inbox/{item_id}")

    # --- assistant (M20: proposals and explanations only) ----------------------

    def assistant_status(self) -> dict:
        return self._request("GET", "/assistant/status")

    def assistant_plan(self, text: str) -> dict:
        return self._request("POST", "/assistant/plan", {"text": text})

    def assistant_explain_day(self) -> dict:
        return self._request("POST", "/assistant/explain-day", {})

    # --- intelligence layer (setup + settings) ------------------------------

    def assistant_setup(self) -> dict:
        """Hardware, model recommendations, Ollama state — one call."""
        return self._request("GET", "/assistant/setup")

    def assistant_ollama(self) -> dict:
        return self._request("GET", "/assistant/ollama")

    def assistant_ollama_pull(self, model: str) -> dict:
        return self._request(
            "POST", "/assistant/ollama/pull", {"model": model}
        )

    def assistant_config(self) -> dict:
        return self._request("GET", "/assistant/config")

    def set_assistant_config(
        self,
        provider: str,
        model: str | None = None,
        api_key: str | None = None,
    ) -> dict:
        body: dict = {"provider": provider}
        if model:
            body["model"] = model
        if api_key:
            body["api_key"] = api_key
        return self._request("PUT", "/assistant/config", body)

    def assistant_test(self) -> dict:
        return self._request("POST", "/assistant/test", {})

    def mobile_pairing_start(self) -> dict:
        """Desktop-side: a 6-digit code the phone enters to pair."""
        return self._request("POST", "/mobile/pairing/start", {})

    def mobile_devices(self) -> list[dict]:
        return self._request("GET", "/mobile/pairing/devices")["devices"]

    def mobile_revoke_device(self, device_id: str) -> dict:
        return self._request(
            "DELETE", f"/mobile/pairing/devices/{device_id}"
        )

    # --- backups (M20) ------------------------------------------------------

    def list_backups(self) -> list[dict]:
        return self._request("GET", "/backups")["backups"]

    def create_backup(self) -> dict:
        return self._request("POST", "/backups", {})

    def restore_backup(self, archive: str) -> dict:
        return self._request("POST", "/backups/restore", {"archive": archive})


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
