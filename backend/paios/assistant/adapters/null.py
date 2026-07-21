"""NullAdapter: the deterministic offline adapter.

Returns a canned, contract-conforming JSON reply derived purely from
the request — identical request, identical reply. Serves tests, demos,
and environments without any LLM SDK; it makes the whole assistant
pipeline runnable end to end with zero network and zero dependencies.
"""

import json

from paios.assistant.adapters import LlmAdapter


class NullAdapter(LlmAdapter):
    @property
    def name(self) -> str:
        return "null"

    def complete(self, request) -> str:
        return json.dumps(
            {
                "answer": (
                    f"[offline] No language model is configured; this is "
                    f"the deterministic null answer for task "
                    f"{request.task.value}. The prepared context contained "
                    f"{len(request.user_prompt)} characters."
                ),
                "bullets": [
                    f"task={request.task.value}",
                    f"template={request.template_name}",
                ],
                "confidence": None,
            }
        )
