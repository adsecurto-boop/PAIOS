"""Anthropic adapter: AssistantRequest -> Claude -> raw text.

Translation only. The SDK is imported lazily; a pre-built client can be
injected (tests use a fake). Defaults follow current Claude API
guidance: model ``claude-opus-4-8`` with adaptive thinking.
"""

import os

from paios.assistant.adapters import (
    AdapterError,
    AdapterUnavailableError,
    LlmAdapter,
)

DEFAULT_MODEL = "claude-opus-4-8"
API_KEY_VARIABLE = "ANTHROPIC_API_KEY"


class AnthropicAdapter(LlmAdapter):
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 4096,
        client=None,
    ) -> None:
        self._model = model
        self._max_tokens = max_tokens
        if client is not None:
            self._client = client
            return
        try:
            import anthropic
        except ImportError as error:
            raise AdapterUnavailableError(
                "The 'anthropic' SDK is not installed (pip install"
                " anthropic)"
            ) from error
        key = api_key if api_key is not None else os.environ.get(
            API_KEY_VARIABLE
        )
        if not key:
            # Without this guard the SDK raises its own error type at
            # construction, which callers cannot map to the fallback.
            raise AdapterUnavailableError(f"{API_KEY_VARIABLE} is not set")
        self._client = anthropic.Anthropic(api_key=key)

    @property
    def name(self) -> str:
        return f"anthropic:{self._model}"

    def complete(self, request) -> str:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                thinking={"type": "adaptive"},
                system=request.system_prompt,
                messages=[{"role": "user", "content": request.user_prompt}],
            )
        except Exception as error:  # SDK errors become adapter errors
            raise AdapterError(f"Anthropic request failed: {error}") from error
        if getattr(response, "stop_reason", None) == "refusal":
            raise AdapterError("Anthropic declined the request (refusal)")
        text = "".join(
            getattr(block, "text", "")
            for block in getattr(response, "content", ())
            if getattr(block, "type", "") == "text"
        )
        if not text:
            raise AdapterError("Anthropic returned no text content")
        return text
