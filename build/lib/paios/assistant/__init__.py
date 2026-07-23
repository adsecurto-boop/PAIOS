"""PAIOS AI Assistant (Milestone 17) — a language layer, nothing more.

    Snapshots -> ContextBuilder -> PromptTemplate -> LlmAdapter -> Parser
                                                           |
                                          immutable AssistantResult DTOs

The assistant explains, summarizes, compares, and answers. It never
decides: the Decision Engine remains the only authority, exactly as the
GUI visualizes without deciding. It receives immutable snapshots and
plain collections, duck-types them (the serialization convention), and
imports NOTHING from the rest of PAIOS — no runtime, scheduler,
decision engine, learning engine, repositories, daemon, or application.
It never mutates, persists, or triggers anything.
"""

from paios.assistant.adapters import (
    AdapterError,
    AdapterUnavailableError,
    LlmAdapter,
)
from paios.assistant.adapters.null import NullAdapter
from paios.assistant.orchestrator import (
    AssistantOrchestrator,
    AssistantRequest,
    AssistantResult,
)
from paios.assistant.response_parser import ParsedResponse, ResponseParseError
from paios.assistant.tools import AssistantTask, SnapshotComparison

__all__ = [
    "AdapterError",
    "AdapterUnavailableError",
    "AssistantOrchestrator",
    "AssistantRequest",
    "AssistantResult",
    "AssistantTask",
    "LlmAdapter",
    "NullAdapter",
    "ParsedResponse",
    "ResponseParseError",
    "SnapshotComparison",
]
