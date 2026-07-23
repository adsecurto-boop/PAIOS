"""Health checks: read-only diagnostics over public surfaces.

Each check returns HealthCheck(component, ok, detail). The application
check boots a real Application against the configured store and stops
it again — the deepest possible "will it run" probe without mutating
domain state (boot loads aggregates; it does not change them).
"""

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.system.config import SystemConfig
from paios.system.daemon_runner import daemon_status


@dataclass(frozen=True)
class HealthCheck:
    component: str
    ok: bool
    detail: str


def run_health_checks(
    config: SystemConfig, include_api: bool = True
) -> list[HealthCheck]:
    checks = [_repositories(config)]
    checks.extend(_application_chain(config))
    checks.append(_daemon(config))
    if include_api:
        checks.append(_api(config))
    return checks


def _repositories(config: SystemConfig) -> HealthCheck:
    data_dir = Path(config.data_dir)
    if not data_dir.is_dir():
        return HealthCheck(
            "repositories",
            True,
            f"store not initialized yet ({data_dir}); first start creates it",
        )
    broken = []
    count = 0
    for store_file in sorted(data_dir.glob("*.json")):
        count += 1
        try:
            json.loads(store_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            broken.append(f"{store_file.name}: {error}")
    if broken:
        return HealthCheck("repositories", False, "; ".join(broken))
    return HealthCheck(
        "repositories", True, f"{count} store file(s) parse cleanly"
    )


def _application_chain(config: SystemConfig) -> list[HealthCheck]:
    """Boot -> inspect application, scheduler, clock, event bus -> stop."""
    try:
        application = Application(ApplicationConfig(data_dir=config.data_dir))
        application.start()
    except Exception as error:
        failure = HealthCheck("application", False, f"start failed: {error}")
        skipped = "skipped (application failed to start)"
        return [
            failure,
            HealthCheck("scheduler", False, skipped),
            HealthCheck("clock", False, skipped),
            HealthCheck("event bus", False, skipped),
        ]
    checks: list[HealthCheck] = []
    try:
        status = application.status()
        checks.append(
            HealthCheck(
                "application",
                status.is_operational,
                f"kernel={status.state.value}"
                f" aggregates={sum(status.aggregate_counts.values())}",
            )
        )
        checks.append(
            HealthCheck(
                "scheduler", True, f"state={application.scheduler_state().value}"
            )
        )
        now = application.components.clock.now()
        checks.append(HealthCheck("clock", True, f"now={now.isoformat()}"))
        bus = application.components.kernel.event_bus
        from paios.runtime.system_events import SystemEventType

        subscribers = sum(
            bus.subscriber_count(event_type)
            for event_type in SystemEventType
        )
        checks.append(
            HealthCheck("event bus", True, f"{subscribers} subscription(s)")
        )
    except Exception as error:  # diagnostics never crash
        checks.append(HealthCheck("application", False, f"probe failed: {error}"))
    finally:
        if application.started:
            application.stop()
    return checks


def _daemon(config: SystemConfig) -> HealthCheck:
    status = daemon_status(config)
    return HealthCheck("daemon", True, status)


def _api(config: SystemConfig) -> HealthCheck:
    url = f"http://{config.server_host}:{config.server_port}/status"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        operational = payload.get("operational") is True
        return HealthCheck(
            "api",
            operational,
            f"{url} answered (operational={payload.get('operational')})",
        )
    except (urllib.error.URLError, OSError, ValueError):
        return HealthCheck(
            "api", True, f"not serving on {url} (start with `paios serve`)"
        )
