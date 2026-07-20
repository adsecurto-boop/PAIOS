"""Reconstitution surface: TransitionHistory.from_records + restore factories.

Hydration restores evidence; it never re-executes commands. These tests pin
the structural validation, the evidence-shape rules, and the guarantee that
every immutability guard is armed on reconstituted aggregates.
"""

import pytest

from paios.domain.entities.context_window import ContextWindow
from paios.domain.entities.event import Event
from paios.domain.entities.event_disturber import EventDisturber
from paios.domain.entities.recommendation import Recommendation
from paios.domain.enums import (
    ContextWindowState,
    DisturberResolutionStatus,
    DisturberSeverity,
    DisturberState,
    DisturberType,
    EventOutcomeType,
    EventStatus,
    RecommendationStatus,
)
from paios.domain.errors import (
    DomainValidationError,
    ImmutabilityViolationError,
    InvalidTransitionError,
)
from paios.domain.state_machines.definitions import EVENT_STATE_MACHINE
from paios.domain.state_machines.machine import TransitionHistory, TransitionRecord
from paios.domain.value_objects.event_outcome import EventOutcome
from paios.domain.value_objects.identifiers import (
    ContextId,
    ContextWindowId,
    EventDisturberId,
    EventId,
    RecommendationId,
    ReflectionId,
    UserId,
)

from tests.domain.conftest import T0, at


def records(*steps: tuple[EventStatus, EventStatus]) -> tuple:
    return tuple(
        TransitionRecord(source, target, at(index), "Scheduler")
        for index, (source, target) in enumerate(steps, start=1)
    )

COMPLETED_CHAIN = records(
    (EventStatus.RECOMMENDED, EventStatus.SCHEDULED),
    (EventStatus.SCHEDULED, EventStatus.READY),
    (EventStatus.READY, EventStatus.STARTED),
    (EventStatus.STARTED, EventStatus.COMPLETED),
)


def restore_event(transitions=COMPLETED_CHAIN, **overrides) -> Event:
    parameters = dict(
        event_id=EventId("evt_001"),
        user_id=UserId("user_001"),
        context_window_id=ContextWindowId("win_001"),
        category="study",
        description="Studied ISTQB Chapter 3",
        transitions=transitions,
    )
    parameters.update(overrides)
    return Event.restore(**parameters)


class TestFromRecords:
    def test_valid_chain_restores_state_and_order(self):
        history = TransitionHistory.from_records(
            EVENT_STATE_MACHINE, EventStatus.RECOMMENDED, COMPLETED_CHAIN
        )
        assert history.current_state is EventStatus.COMPLETED
        assert history.records == COMPLETED_CHAIN

    def test_empty_records_mean_initial_state(self):
        history = TransitionHistory.from_records(
            EVENT_STATE_MACHINE, EventStatus.RECOMMENDED, ()
        )
        assert history.current_state is EventStatus.RECOMMENDED
        assert history.records == ()

    def test_broken_continuity_rejected(self):
        broken = records(
            (EventStatus.RECOMMENDED, EventStatus.SCHEDULED),
            (EventStatus.READY, EventStatus.STARTED),  # skips Scheduled->Ready
        )
        with pytest.raises(InvalidTransitionError, match="from_state"):
            TransitionHistory.from_records(
                EVENT_STATE_MACHINE, EventStatus.RECOMMENDED, broken
            )

    def test_illegal_edge_rejected(self):
        illegal = records((EventStatus.RECOMMENDED, EventStatus.COMPLETED))
        with pytest.raises(InvalidTransitionError):
            TransitionHistory.from_records(
                EVENT_STATE_MACHINE, EventStatus.RECOMMENDED, illegal
            )

    def test_reconstituted_history_stays_append_only(self):
        history = TransitionHistory.from_records(
            EVENT_STATE_MACHINE, EventStatus.RECOMMENDED, COMPLETED_CHAIN
        )
        history.apply(EventStatus.ARCHIVED, at(10), "Scheduler")
        assert history.current_state is EventStatus.ARCHIVED
        assert len(history.records) == 5


class TestEventRestore:
    def test_restores_state_and_evidence(self):
        event = restore_event(
            outcome=EventOutcome(EventOutcomeType.COMPLETED, at(5)),
            reflection_id=ReflectionId("ref_001"),
        )
        assert event.status is EventStatus.COMPLETED
        assert event.outcome.outcome_type is EventOutcomeType.COMPLETED
        assert event.reflection_id == ReflectionId("ref_001")

    def test_guards_are_armed_after_restore(self):
        event = restore_event()
        with pytest.raises(ImmutabilityViolationError):
            event.description = "rewritten history"
        with pytest.raises(ImmutabilityViolationError):
            event._history = TransitionHistory(
                EVENT_STATE_MACHINE, EventStatus.RECOMMENDED
            )

    def test_life_continues_after_restore(self):
        event = restore_event()
        record = event.transition_to(EventStatus.ARCHIVED, at(10))
        assert record.from_state is EventStatus.COMPLETED
        assert len(event.transitions) == 5

    def test_outcome_survives_archival_evidence(self):
        # The case replay could not express directly: outcome recorded while
        # Completed, event since Archived. Evidence-shape accepts it.
        chain = COMPLETED_CHAIN + (
            TransitionRecord(
                EventStatus.COMPLETED, EventStatus.ARCHIVED, at(9), "Scheduler"
            ),
        )
        event = restore_event(
            transitions=chain,
            outcome=EventOutcome(EventOutcomeType.COMPLETED, at(5)),
        )
        assert event.status is EventStatus.ARCHIVED
        assert event.outcome is not None

    def test_outcome_without_qualifying_history_rejected(self):
        with pytest.raises(DomainValidationError, match="Outcome evidence"):
            restore_event(
                transitions=records(
                    (EventStatus.RECOMMENDED, EventStatus.SCHEDULED)
                ),
                outcome=EventOutcome(EventOutcomeType.COMPLETED, at(5)),
            )

    def test_reflection_without_completion_rejected(self):
        with pytest.raises(DomainValidationError, match="Reflection evidence"):
            restore_event(
                transitions=records(
                    (EventStatus.RECOMMENDED, EventStatus.SCHEDULED)
                ),
                reflection_id=ReflectionId("ref_001"),
            )


class TestContextWindowRestore:
    def test_expired_window_is_fact_frozen_on_return(self):
        window = ContextWindow.restore(
            window_id=ContextWindowId("win_001"),
            context_id=ContextId("ctx_001"),
            event_id=EventId("evt_001"),
            start_time=T0,
            end_time=at(60),
            transitions=(
                TransitionRecord(
                    ContextWindowState.CREATED,
                    ContextWindowState.ACTIVE,
                    T0,
                    "Runtime",
                ),
                TransitionRecord(
                    ContextWindowState.ACTIVE,
                    ContextWindowState.EXPIRED,
                    at(60),
                    "Runtime",
                ),
            ),
        )
        assert window.current_state is ContextWindowState.EXPIRED
        with pytest.raises(ImmutabilityViolationError):
            window.start_time = at(999)


class TestRecommendationRestore:
    def test_evidence_is_not_readjudicated_by_present_policy(self):
        # Historically accepted AFTER expires_at (e.g. recorded under an
        # earlier expiry Policy). Policies evolve; history must still load.
        recommendation = Recommendation.restore(
            recommendation_id=RecommendationId("rec_001"),
            user_id=UserId("user_001"),
            reason="Historical suggestion",
            created_at=T0,
            expires_at=at(30),
            transitions=(
                TransitionRecord(
                    RecommendationStatus.GENERATED,
                    RecommendationStatus.PENDING,
                    at(1),
                    "Runtime",
                ),
                TransitionRecord(
                    RecommendationStatus.PENDING,
                    RecommendationStatus.ACCEPTED,
                    at(45),  # after expires_at — evidence, not a new command
                    "Scheduler",
                ),
            ),
        )
        assert recommendation.status is RecommendationStatus.ACCEPTED

    def test_new_commands_still_enforce_policy_after_restore(self):
        recommendation = Recommendation.restore(
            recommendation_id=RecommendationId("rec_002"),
            user_id=UserId("user_001"),
            reason="Pending suggestion",
            created_at=T0,
            expires_at=at(30),
            transitions=(
                TransitionRecord(
                    RecommendationStatus.GENERATED,
                    RecommendationStatus.PENDING,
                    at(1),
                    "Runtime",
                ),
            ),
        )
        from paios.domain.errors import RecommendationExpiredError

        with pytest.raises(RecommendationExpiredError):
            recommendation.accept(at(60))


class TestEventDisturberRestore:
    APPLIED_CHAIN = (
        TransitionRecord(
            DisturberState.DETECTED, DisturberState.RECORDED, at(1), "Runtime"
        ),
        TransitionRecord(
            DisturberState.RECORDED, DisturberState.ANALYZED, at(2), "Runtime"
        ),
        TransitionRecord(
            DisturberState.ANALYZED, DisturberState.APPLIED, at(3), "Runtime"
        ),
    )

    def restore(self, **overrides) -> EventDisturber:
        parameters = dict(
            event_disturber_id=EventDisturberId("dist_001"),
            user_id=UserId("user_001"),
            type=DisturberType.WORK,
            description="Team Lead requested overtime",
            severity=DisturberSeverity.HIGH,
            occurred_at=T0,
            resulting_context_window_id=ContextWindowId("win_002"),
            transitions=self.APPLIED_CHAIN,
        )
        parameters.update(overrides)
        return EventDisturber.restore(**parameters)

    def test_applied_disturber_restores(self):
        disturber = self.restore()
        assert disturber.state is DisturberState.APPLIED
        assert disturber.resulting_context_window_id == ContextWindowId("win_002")

    def test_applied_without_window_reference_rejected(self):
        with pytest.raises(DomainValidationError, match="Context Window"):
            self.restore(resulting_context_window_id=None)

    def test_resolution_status_must_agree_with_evidence(self):
        with pytest.raises(DomainValidationError, match="resolution status"):
            self.restore(
                resolution_status=DisturberResolutionStatus.RESOLVED
            )
