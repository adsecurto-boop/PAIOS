"""M20 assistant tasks: proposal parsing and day-plan explanation.

The orchestrator gains two voices; both remain speech-only. A fake
adapter proves the pipeline; the parser proves the strict contract.
"""

import json

import pytest

from paios.assistant.orchestrator import AssistantOrchestrator
from paios.assistant.response_parser import (
    ResponseParseError,
    parse_planning_response,
)
from paios.assistant.tools import AssistantTask


class FakeAdapter:
    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.requests = []

    @property
    def name(self) -> str:
        return "fake"

    def complete(self, request) -> str:
        self.requests.append(request)
        return self.reply


PROPOSAL_REPLY = json.dumps(
    {
        "answer": "Classified 2 lines.",
        "items": [
            {
                "text": "Temple",
                "kind": "event",
                "title": "Temple",
                "day_scope": "tomorrow",
                "duplicate_of": None,
                "notes": "single concrete action",
            },
            {
                "text": "Build PAIOS",
                "kind": "project",
                "title": "Build PAIOS",
                "day_scope": None,
                "duplicate_of": "PAIOS",
                "notes": "matches existing project",
            },
        ],
        "questions": ["Which chapter?"],
        "confidence": 0.9,
    }
)


class TestClassifyCaptures:
    def test_pipeline_renders_context_and_parses_items(self):
        adapter = FakeAdapter(PROPOSAL_REPLY)
        orchestrator = AssistantOrchestrator(adapter)
        proposal = orchestrator.classify_captures(
            "Tomorrow\nTemple\nBuild PAIOS",
            existing_projects=("PAIOS",),
        )
        assert proposal.task is AssistantTask.CLASSIFY_CAPTURE
        assert [item.kind for item in proposal.items] == [
            "event", "project",
        ]
        assert proposal.items[1].duplicate_of == "PAIOS"
        assert proposal.questions == ("Which chapter?",)
        request = adapter.requests[0]
        assert "Temple" in request.user_prompt
        assert "PAIOS" in request.user_prompt
        assert "never create" in request.system_prompt.lower() or (
            "never creates" in request.system_prompt.lower()
        )

    def test_malformed_reply_raises_parse_error(self):
        orchestrator = AssistantOrchestrator(FakeAdapter("not json"))
        with pytest.raises(ResponseParseError):
            orchestrator.classify_captures("Gym")


class TestExplainDayPlan:
    def test_uses_standard_contract(self):
        reply = json.dumps(
            {
                "answer": "Temple first: lowest energy requirement.",
                "bullets": ["Temple 7:30 - low energy"],
                "confidence": 0.8,
            }
        )
        orchestrator = AssistantOrchestrator(FakeAdapter(reply))
        result = orchestrator.explain_day_plan(
            ["07:30 Temple (60m)"], ["Temple: low energy task"]
        )
        assert result.task is AssistantTask.EXPLAIN_DAY_PLAN
        assert "Temple" in result.answer


class TestParsePlanningResponse:
    def test_fenced_json_accepted(self):
        parsed = parse_planning_response(
            "```json\n" + PROPOSAL_REPLY + "\n```"
        )
        assert len(parsed.items) == 2

    @pytest.mark.parametrize(
        "mutation",
        [
            {"items": "not-a-list"},
            {"items": [{"text": "x", "kind": "habit", "title": "x"}]},
            {"items": [{"kind": "event", "title": "x"}]},
            {"questions": "not-a-list"},
            {"confidence": 1.5},
            {"answer": ""},
        ],
    )
    def test_contract_violations_rejected(self, mutation):
        payload = json.loads(PROPOSAL_REPLY)
        payload.update(mutation)
        with pytest.raises(ResponseParseError):
            parse_planning_response(json.dumps(payload))
