"""The REST client: the GUI's single doorway into PAIOS.

Pure stdlib (urllib) — no paios imports, no third-party HTTP library.
One method per REST endpoint the GUI uses; every GUI action maps to
exactly one method here, and every method issues exactly one request.

Failures become one of three exceptions:

- ApiUnreachable  — connection refused / reset / DNS failure (the server
  is down or the network is gone); the window shows the offline banner
  and keeps retrying on its poll timer.
- ApiTimeout      — a SUBCLASS of ApiUnreachable: the server accepted the
  connection but did not answer inside the deadline. That is not the
  same fact as "unreachable", and conflating them is what made a slow
  model round trip report "Offline" for a server that was answering.
  Callers that care (the AI surfaces) catch it first; the poll loop
  keeps treating it as an outage, which is right for a poll.
- ApiResponseError — the server answered with an error payload
  (validation failure, unknown entity, conflict); carries the HTTP
  status and the API's ``{"error": {"type", "message"}}`` fields.

Timeouts are per call, not per client: polling wants a short deadline so
a hung server cannot hang the window, while an AI round trip legitimately
runs for minutes (the backend's Ollama adapter allows 300 s). One number
cannot serve both, so every method that can be slow names its own.
"""

import json
import logging
import socket
import time
import urllib.error
import urllib.request

logger = logging.getLogger("paios.gui")

#: Deadline for calls that make the backend talk to an AI provider. It
#: matches the backend's own completion ceiling, so the client never
#: gives up on a request the server is still working on.
AI_REQUEST_TIMEOUT_SECONDS = 300.0
#: Deadline for backend calls that probe the local Ollama server. The
#: backend allows those 4 s, plus room for its own round trip.
PROBE_TIMEOUT_SECONDS = 15.0


class ApiUnreachable(Exception):
    """The server could not be reached at all."""


class ApiTimeout(ApiUnreachable):
    """The server was reached but did not answer inside the deadline."""

    def __init__(self, seconds: float, detail: str = "") -> None:
        super().__init__(
            f"no answer within {seconds:g}s"
            + (f" ({detail})" if detail else "")
        )
        self.seconds = seconds


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

    @property
    def timeout(self) -> float:
        return self._timeout

    # --- transport -------------------------------------------------------

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        timeout: float | None = None,
    ):
        deadline = self._timeout if timeout is None else timeout
        data = None
        headers = {"Accept": "application/json"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = urllib.request.Request(
            self._base_url + path, data=data, headers=headers, method=method
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=deadline) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            failure = _response_error(error)
            logger.info(
                "api %s %s -> HTTP %s %s (%.0f ms)",
                method, path, failure.status, failure,
                (time.perf_counter() - started) * 1000,
            )
            raise failure from error
        except (socket.timeout, TimeoutError) as error:
            logger.info(
                "api %s %s -> timeout after %gs", method, path, deadline
            )
            raise ApiTimeout(deadline, str(error) or "read timed out") from error
        except urllib.error.URLError as error:
            # urllib wraps a socket timeout in URLError too; keep the
            # distinction rather than flattening both to "unreachable".
            if isinstance(error.reason, (socket.timeout, TimeoutError)):
                logger.info(
                    "api %s %s -> timeout after %gs", method, path, deadline
                )
                raise ApiTimeout(deadline, str(error.reason)) from error
            logger.info("api %s %s -> unreachable: %s", method, path, error)
            raise ApiUnreachable(str(error)) from error
        except OSError as error:
            logger.info("api %s %s -> unreachable: %s", method, path, error)
            raise ApiUnreachable(str(error)) from error
        logger.debug(
            "api %s %s -> 200 (%.0f ms)",
            method, path, (time.perf_counter() - started) * 1000,
        )
        return payload

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
        # Reaches the provider when one is configured.
        return self._request(
            "POST", "/assistant/plan", {"text": text},
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )

    def assistant_explain_day(self) -> dict:
        return self._request(
            "POST", "/assistant/explain-day", {},
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )

    # --- intelligence layer (setup + settings) ------------------------------

    def assistant_setup(self) -> dict:
        """Hardware, model recommendations, Ollama state — one call."""
        return self._request(
            "GET", "/assistant/setup", timeout=PROBE_TIMEOUT_SECONDS
        )

    def assistant_ollama(self) -> dict:
        return self._request(
            "GET", "/assistant/ollama", timeout=PROBE_TIMEOUT_SECONDS
        )

    def assistant_ollama_pull(self, model: str) -> dict:
        return self._request(
            "POST", "/assistant/ollama/pull", {"model": model},
            timeout=PROBE_TIMEOUT_SECONDS,
        )

    def assistant_ollama_remove(self, model: str) -> dict:
        return self._request(
            "POST", "/assistant/ollama/remove", {"model": model},
            timeout=PROBE_TIMEOUT_SECONDS,
        )

    def assistant_ollama_show(self, model: str) -> dict:
        """Context length, parameter size and quantization for a model."""
        return self._request(
            "POST", "/assistant/ollama/show", {"model": model},
            timeout=PROBE_TIMEOUT_SECONDS,
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
        # Applying a provider recomposes the assistant server-side, which
        # probes the provider — slower than a plain read.
        return self._request(
            "PUT", "/assistant/config", body,
            timeout=PROBE_TIMEOUT_SECONDS,
        )

    def assistant_test(self) -> dict:
        """One real round trip through the configured provider.

        A 7B model on CPU answers in tens of seconds, so this deliberately
        does NOT use the client's short polling deadline — giving up after
        2 s and calling the result "Offline" was the bug, not the cure.
        """
        return self._request(
            "POST", "/assistant/test", {},
            timeout=AI_REQUEST_TIMEOUT_SECONDS,
        )

    # --- networking (M21: the Networking page) ------------------------------

    def system_network(self) -> dict:
        """Current IP, port, mode, firewall and Wi-Fi — one call."""
        return self._request("GET", "/system/network")

    def set_network_mode(self, mode: str) -> dict:
        """Switch between 'local' (loopback only) and 'lan' (reachable
        by paired phones). Loopback-only on the server side."""
        return self._request("PUT", "/system/network", {"mode": mode})

    def open_firewall(self) -> dict:
        return self._request("POST", "/system/network/firewall", {})

    def system_server(self) -> dict:
        return self._request("GET", "/system/server")

    def system_relay(self) -> dict:
        """Remote-access (relay) settings + live connection status."""
        return self._request("GET", "/system/relay")

    def set_relay_config(
        self,
        enabled: bool | None = None,
        relay_url: str | None = None,
        account: str | None = None,
        account_key: str | None = None,
    ) -> dict:
        body: dict = {}
        if enabled is not None:
            body["enabled"] = enabled
        if relay_url is not None:
            body["relay_url"] = relay_url
        if account is not None:
            body["account"] = account
        if account_key:
            body["account_key"] = account_key
        return self._request("PUT", "/system/relay", body)

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
