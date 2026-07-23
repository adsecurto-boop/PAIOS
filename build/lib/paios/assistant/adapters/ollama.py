"""Ollama adapter: AssistantRequest -> local model -> raw text.

The free, private, offline default of the PAIOS intelligence layer.
Talks to a locally running Ollama server (https://ollama.com) over
plain HTTP — stdlib urllib only, no SDK, no API key, no cloud.

Translation only, like every adapter. The transport is injectable so
the whole adapter is testable without a running server. Construction
probes the server once: an unreachable Ollama raises
AdapterUnavailableError, and composition falls back to the heuristic
path — PAIOS never blocks on a missing model server.
"""

import json
import os
import urllib.error
import urllib.request

from paios.assistant.adapters import (
    AdapterError,
    AdapterUnavailableError,
    LlmAdapter,
)

DEFAULT_MODEL = "qwen2.5:7b"
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
BASE_URL_VARIABLE = "PAIOS_OLLAMA_URL"

_PROBE_TIMEOUT_SECONDS = 3
_COMPLETION_TIMEOUT_SECONDS = 300


def default_transport(url: str, payload: dict | None, timeout: float):
    """One HTTP exchange: GET when payload is None, else POST JSON.
    Returns the decoded JSON reply. The single seam tests replace."""
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read().decode("utf-8"))


def resolve_base_url(base_url: str | None = None) -> str:
    return (
        base_url
        or os.environ.get(BASE_URL_VARIABLE)
        or DEFAULT_BASE_URL
    ).rstrip("/")


class OllamaAdapter(LlmAdapter):
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        base_url: str | None = None,
        timeout: float = _COMPLETION_TIMEOUT_SECONDS,
        transport=None,
    ) -> None:
        self._model = model
        self._base_url = resolve_base_url(base_url)
        self._timeout = timeout
        self._transport = (
            transport if transport is not None else default_transport
        )
        try:
            self._transport(
                f"{self._base_url}/api/version", None, _PROBE_TIMEOUT_SECONDS
            )
        except Exception as error:
            raise AdapterUnavailableError(
                f"Ollama is not reachable at {self._base_url} — install"
                " it from https://ollama.com and make sure it is running"
            ) from error

    @property
    def name(self) -> str:
        return f"ollama:{self._model}"

    def complete(self, request) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": request.system_prompt},
                {"role": "user", "content": request.user_prompt},
            ],
        }
        try:
            reply = self._transport(
                f"{self._base_url}/api/chat", payload, self._timeout
            )
        except urllib.error.HTTPError as error:
            detail = ""
            try:
                detail = error.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            if error.code == 404:
                raise AdapterError(
                    f"Ollama has no model {self._model!r} — pull it with"
                    f" `ollama pull {self._model}` ({detail})"
                ) from error
            raise AdapterError(
                f"Ollama request failed ({error.code}): {detail}"
            ) from error
        except Exception as error:
            raise AdapterError(f"Ollama request failed: {error}") from error
        text = (reply.get("message") or {}).get("content", "")
        if not text:
            raise AdapterError("Ollama returned no text content")
        return text
