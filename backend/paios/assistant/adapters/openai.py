"""OpenAI adapter: AssistantRequest -> chat completion -> raw text.

Translation only; lazy SDK import; injectable client for tests.
"""

import os

from paios.assistant.adapters import (
    AdapterError,
    AdapterUnavailableError,
    AIProvider,
    LlmAdapter,
    ProviderCapabilities,
)

DEFAULT_MODEL = "gpt-4o"
API_KEY_VARIABLE = "OPENAI_API_KEY"


class OpenAIAdapter(AIProvider):
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
            import openai
        except ImportError as error:
            raise AdapterUnavailableError(
                "The 'openai' SDK is not installed (pip install openai)"
            ) from error
        key = api_key if api_key is not None else os.environ.get(
            API_KEY_VARIABLE
        )
        if not key:
            # Without this guard the SDK raises its own error type at
            # construction, which callers cannot map to the fallback.
            raise AdapterUnavailableError(f"{API_KEY_VARIABLE} is not set")
        self._client = openai.OpenAI(api_key=key)

    @property
    def capabilities(self) -> ProviderCapabilities:
        from paios.assistant.adapters import ProviderCapabilities
        return ProviderCapabilities(
            streaming=True,
            vision=True,
            tool_calling=True
        )

    def health_check(self) -> tuple[bool, str]:
        if not getattr(self, "_client", None):
            return False, "OpenAI client not initialized"
        if not self._client.api_key:
            return False, f"{API_KEY_VARIABLE} is not set"
        return True, "Ready"

    @property
    def name(self) -> str:
        return f"openai:{self._model}"

    def complete(self, request) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": request.system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
            )
        except Exception as error:
            raise AdapterError(f"OpenAI request failed: {error}") from error
        choices = getattr(response, "choices", None) or ()
        text = (
            getattr(getattr(choices[0], "message", None), "content", None)
            if choices
            else None
        )
        if not text:
            raise AdapterError("OpenAI returned no text content")
        return text
