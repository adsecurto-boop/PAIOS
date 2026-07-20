"""RecalculationBridge — runtime signals in, one Scheduler trigger out.

Approved refinement 1: the Scheduler subscribes only to
SchedulerRecalculationRequested. This bridge subscribes to the runtime
signal topics and republishes each as a recalculation request carrying a
RecalculationReason, forwarding the original payload untouched.
"""

from paios.runtime.kernel import RuntimeKernel
from paios.runtime.system_events import SystemEvent, SystemEventType
from paios.scheduler.scheduler import RecalculationReason

_REASON_BY_TOPIC: dict[SystemEventType, RecalculationReason] = {
    SystemEventType.TIME_PROGRESSED: RecalculationReason.TIME_PROGRESSED,
    SystemEventType.CONTEXT_CHANGED: RecalculationReason.CONTEXT_CHANGED,
    SystemEventType.DISTURBANCE_DETECTED: (
        RecalculationReason.DISTURBANCE_DETECTED
    ),
    SystemEventType.RECOMMENDATION_GENERATED: (
        RecalculationReason.RECOMMENDATION_GENERATED
    ),
}


class RecalculationBridge:
    def __init__(self, kernel: RuntimeKernel) -> None:
        self._kernel = kernel
        self._attached = False

    def attach(self) -> None:
        if self._attached:
            return
        for topic in _REASON_BY_TOPIC:
            self._kernel.event_bus.subscribe(topic, self._forward)
        self._attached = True

    def _forward(self, event: SystemEvent) -> None:
        payload = dict(event.payload)
        payload["reason"] = _REASON_BY_TOPIC[event.event_type].value
        self._kernel.event_bus.publish(
            SystemEvent(
                event_type=SystemEventType.SCHEDULER_RECALCULATION_REQUESTED,
                occurred_at=event.occurred_at,
                payload=payload,
            )
        )
