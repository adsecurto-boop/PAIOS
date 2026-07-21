"""OpenAI adapter: AssistantRequest -> chat completion -> raw text.

Translation only; lazy SDK import; injectable client for tests.
"""

from paios.assistant.adapters import (
    AdapterError,
    AdapterUnavailableError,
    LlmAdapter,
)

DEFAULT_MODEL = "gpt-4o"


class OpenAIAdapter(LlmAdapter):
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
        self._client = (
            openai.OpenAI(api_key=api_key)
            if api_key is not None
            else openai.OpenAI()
        )

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
