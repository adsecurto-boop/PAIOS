"""Gemini adapter/provider: AssistantRequest -> Google Gemini API -> raw text.

Uses direct HTTPS calls over urllib stdlib, keeping PAIOS dependency-free.
"""

import json
import os
import urllib.error
import urllib.request

from paios.assistant.adapters import (
    AdapterError,
    AdapterUnavailableError,
    AIProvider,
    ProviderCapabilities,
)

DEFAULT_MODEL = "gemini-2.5-flash"
API_KEY_VARIABLE = "GEMINI_API_KEY"


def default_transport(url: str, payload: dict | None, headers: dict, timeout: float):
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers,
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as reply:
        return json.loads(reply.read().decode("utf-8"))


class GeminiProvider(AIProvider):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        timeout: float = 30.0,
        transport=None,
    ) -> None:
        self._model = model
        self._timeout = timeout
        self._transport = (
            transport if transport is not None else default_transport
        )
        self._api_key = api_key if api_key is not None else os.environ.get(
            API_KEY_VARIABLE
        )
        if not self._api_key:
            raise AdapterUnavailableError(f"{API_KEY_VARIABLE} is not set")
        self._last_prompt_tokens = 0
        self._last_completion_tokens = 0

    @property
    def name(self) -> str:
        return f"gemini:{self._model}"

    @property
    def capabilities(self) -> ProviderCapabilities:
        from paios.assistant.adapters import ProviderCapabilities
        return ProviderCapabilities(
            streaming=True,
            vision=True,
            tool_calling=True,
            thinking=True
        )

    def health_check(self) -> tuple[bool, str]:
        if not self._api_key:
            return False, f"{API_KEY_VARIABLE} is not set"
        # Endpoint to fetch model info (lightweight metadata check)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}?key={self._api_key}"
        try:
            self._transport(url, None, {}, 5.0)
            return True, "Ready"
        except Exception as error:
            reason = str(error)
            if isinstance(error, urllib.error.HTTPError):
                if error.code in (401, 403):
                    reason = "Invalid API Key"
                elif error.code == 429:
                    reason = "Quota exceeded"
                elif error.code == 404:
                    reason = "Model unavailable"
            return (
                False,
                f"Gemini API check failed for {self._model}: {reason}",
            )

    def complete(self, request) -> str:
        url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self._model}:generateContent"
        )
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self._api_key,
        }
        payload = {
            "systemInstruction": {
                "parts": [{"text": request.system_prompt}]
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": request.user_prompt}],
                }
            ],
        }
        try:
            reply = self._transport(url, payload, headers, self._timeout)
        except urllib.error.HTTPError as error:
            detail = ""
            try:
                detail = error.read().decode("utf-8", "replace")[:300]
            except Exception:
                pass
            msg = f"Gemini request failed ({error.code}): {detail}"
            if error.code in (401, 403):
                msg = "Invalid API Key"
            elif error.code == 429:
                msg = "Quota exceeded"
            elif error.code == 404:
                msg = "Model unavailable"
            raise AdapterError(msg) from error
        except Exception as error:
            raise AdapterError(f"Gemini request failed: {error}") from error

        try:
            candidates = reply.get("candidates") or []
            if not candidates:
                raise AdapterError("Gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts") or []
            if not parts:
                raise AdapterError("Gemini returned no content parts")
            text = parts[0].get("text", "")
            if not text:
                raise AdapterError("Gemini returned no text content")

            usage = reply.get("usageMetadata") or {}
            self._last_prompt_tokens = usage.get("promptTokenCount", 0)
            self._last_completion_tokens = usage.get("candidatesTokenCount", 0)

            return text
        except Exception as error:
            if isinstance(error, AdapterError):
                raise
            raise AdapterError(
                f"Gemini response parsing failed: {error}"
            ) from error
