"""Prompt determinism and context determinism."""

import pytest

from paios.assistant import context_builder, prompts


class TestTemplates:
    def test_registry_has_the_mission_templates_plus_m20_planning(self):
        assert sorted(prompts.TEMPLATES) == [
            "day_plan_explanation",
            "evening_review",
            "explain",
            "learning_explanation",
            "morning_planning",
            "planning_classification",
            "project_explanation",
            "recommendation_explanation",
            "reflect",
            "summarize",
            "weekly_review",
        ]

    def test_every_template_embeds_exactly_one_reply_contract(self):
        # M20: the planning classification speaks the structured
        # PLANNING_CONTRACT; every other voice keeps RESPONSE_CONTRACT.
        for template in prompts.TEMPLATES.values():
            if template.name == "planning_classification":
                assert prompts.PLANNING_CONTRACT in template.system
                assert prompts.RESPONSE_CONTRACT not in template.system
            else:
                assert prompts.RESPONSE_CONTRACT in template.system

    def test_render_is_deterministic(self):
        first = prompts.EXPLAIN.render(
            subject="s", context="c", question="q"
        )
        second = prompts.EXPLAIN.render(
            question="q", context="c", subject="s"  # different kwarg order
        )
        assert first == second

    def test_missing_field_is_an_error(self):
        with pytest.raises(KeyError, match="missing fields"):
            prompts.EXPLAIN.render(subject="s", context="c")

    def test_unexpected_field_is_an_error(self):
        with pytest.raises(KeyError, match="unexpected fields"):
            prompts.SUMMARIZE.render(scope="x", context="c", extra="boom")


class TestContextDeterminism:
    def test_identical_inputs_identical_text(self, snapshot, events):
        first = context_builder.build_context(
            snapshot=snapshot, events=events
        )
        second = context_builder.build_context(
            snapshot=snapshot, events=events
        )
        assert first == second

    def test_input_order_does_not_matter(self, events):
        forward = context_builder.build_context(events=events)
        backward = context_builder.build_context(events=tuple(reversed(events)))
        assert forward == backward  # sorting makes order canonical

    def test_snapshot_block_reads_duck_typed_fields(self, snapshot):
        block = context_builder.snapshot_block(snapshot)
        assert "Snapshot time: 2026-07-20T09:00:00" in block
        assert "Running event: none (idle)" in block
        assert "Events held: 2" in block

    def test_learning_block(self, learning_result):
        block = context_builder.learning_block(learning_result)
        assert "insights: 1" in block
        assert "Focus rising week over week" in block

    def test_unknown_collection_is_an_error(self, events):
        with pytest.raises(KeyError, match="Unknown context collections"):
            context_builder.build_context(evnts=events)  # typo must not pass

    def test_no_clock_dependence(self, snapshot, monkeypatch):
        # build_context must never consult the wall clock: freeze it and
        # compare against an unfrozen render.
        import datetime as datetime_module

        reference = context_builder.build_context(snapshot=snapshot)

        class FrozenDateTime(datetime_module.datetime):
            @classmethod
            def now(cls, tz=None):  # pragma: no cover - must not be called
                raise AssertionError("context builder consulted the clock")

        monkeypatch.setattr(datetime_module, "datetime", FrozenDateTime)
        assert context_builder.build_context(snapshot=snapshot) == reference

    def test_every_mission_input_renders(
        self,
        recommendation,
        events,
        projects,
        knowledge_items,
        reflections,
        principle,
        habit,
    ):
        text = context_builder.build_context(
            recommendations=(recommendation,),
            events=events,
            goals=(),
            projects=projects,
            resources=(),
            habits=(habit,),
            insights=(),
            principles=(principle,),
            knowledge=knowledge_items,
            reflections=reflections,
            contexts=(),
        )
        for expected in (
            "Recommendations:",
            "Events:",
            "Goals:\n(none)",
            "Projects:",
            "Habits:",
            "Principles:",
            "Knowledge:",
            "Reflections:",
            "rest to recover",
            "Boundary analysis",
            "Health first",
        ):
            assert expected in text
