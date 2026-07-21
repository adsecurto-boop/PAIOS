"""LLM adapters: request/response translation, zero reasoning.

An adapter receives an AssistantRequest (already fully composed system
+ user prompts) and returns the model's raw text. It adds nothing,
filters nothing, and decides nothing. SDKs are imported lazily inside
the concrete adapters — the assistant layer itself stays stdlib-only,
and an environment without a given SDK simply cannot construct that
adapter (AdapterUnavailableError), exactly like M14's DesktopProvider.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # import only for type checkers; no runtime cycle
    from paios.assistant.orchestrator import AssistantRequest


class AdapterError(Exception):
    """The provider failed to answer (network, refusal, API error)."""


class AdapterUnavailableError(AdapterError):
    """The adapter's SDK or credentials are absent in this environment."""


class LlmAdapter(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Stable adapter name (diagnostics; recorded on results)."""

    @abstractmethod
    def complete(self, request: "AssistantRequest") -> str:
        """One request -> the model's raw text. Raise AdapterError on
        failure; never return partial or invented content."""
