"""PlanningService: one object holding the four stores plus the pure
transformations between them (template -> intent, recurrence -> intent,
inbox conversion bookkeeping).

The service never calls the Application facade — the REST layer
composes "service produces an intent" with "facade proposes it", the
same one-delegation-per-handler shape the API has always had.
"""

from datetime import datetime, timedelta
from pathlib import Path

from paios.domain.value_objects.identifiers import ProjectId, UserId
from paios.planning.intents import EventIntent
from paios.planning.stores import (
    WEEKDAYS,
    DailyLogStore,
    EventMetadataStore,
    InboxStore,
    PlanningStoreError,
    RecurrenceStore,
    TemplateStore,
)


class PlanningService:
    def __init__(self, data_dir: Path | str) -> None:
        planning_dir = Path(data_dir) / "planning"
        self.inbox = InboxStore(planning_dir)
        self.metadata = EventMetadataStore(planning_dir)
        self.templates = TemplateStore(planning_dir)
        self.recurrences = RecurrenceStore(planning_dir)
        self.logs = DailyLogStore(planning_dir)

    # --- templates -> intents ---------------------------------------------

    def instantiate_template(
        self,
        template_id: str,
        user_id: UserId,
        suggested_time: datetime | None,
        priority: float | None = None,
        project_id: ProjectId | None = None,
    ) -> tuple[EventIntent, dict]:
        """Template -> (intent, default metadata). The caller proposes the
        intent through the facade and stores the metadata under the
        resulting id."""
        template = self.templates.get(template_id)
        intent = EventIntent(
            user_id=user_id,
            title=template["title"],
            suggested_time=suggested_time,
            priority=priority,
        )
        return intent, dict(template.get("metadata", {}))

    # --- recurrences -> intents ---------------------------------------------

    def due_recurrences(self, now: datetime) -> list[dict]:
        return [
            rule
            for rule in self.recurrences.list()
            if rule.get("enabled", True)
            and datetime.fromisoformat(rule["next_run"]) <= now
        ]

    def expand_recurrence(
        self, rule: dict, user_id: UserId, now: datetime
    ) -> tuple[EventIntent, dict, datetime]:
        """One due rule -> (intent for this occurrence, default metadata,
        the advanced next_run). The caller proposes the intent, then
        persists the advance via ``recurrences.set_next_run`` — split so
        a failed proposal never silently skips an occurrence."""
        occurrence = datetime.fromisoformat(rule["next_run"])
        intent = EventIntent(
            user_id=user_id,
            title=rule["title"],
            suggested_time=occurrence,
        )
        next_run = self.next_occurrence(rule, occurrence)
        return intent, dict(rule.get("metadata", {})), next_run

    @staticmethod
    def next_occurrence(rule: dict, after: datetime) -> datetime:
        """The rule's next firing strictly after ``after`` — deterministic
        walk over the rule's weekdays at its time of day."""
        hour_text, minute_text = rule["time_of_day"].split(":")
        hour, minute = int(hour_text), int(minute_text)
        allowed = {WEEKDAYS.index(day) for day in rule["days"]}
        if not allowed:
            raise PlanningStoreError("Recurrence rule has no weekdays")
        candidate = after.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        for _ in range(15):  # two weeks bounds any weekly pattern
            candidate += timedelta(days=1)
            if candidate.weekday() in allowed and candidate > after:
                return candidate
        raise PlanningStoreError("Recurrence walk failed to advance")
