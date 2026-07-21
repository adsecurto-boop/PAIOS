# Milestone 14 — Notification System

## Mission

Implement PAIOS's notification subsystem as a pure observer: it reacts
to published events and does nothing else — no business logic, no
Runtime/Scheduler/Decision-Engine/Learning mutations.

## 1. Architecture

```
Event Bus  (paios.runtime.event_bus — M3, unchanged)
    │  subscribe (SystemEventType topics)
    ▼
NotificationManager  (backend/paios/notifications/manager.py)
    │  format -> deduplicate -> quiet hours -> route
    ▼
NotificationProvider abstraction
    ├── ConsoleProvider   (text stream)
    ├── DesktopProvider   (Qt system-tray toast; optional dependency)
    └── NullProvider      (silent sink)
         Future: Android / Email / Discord / Slack / Push
```

The manager is attached by **composition roots**, never by the
Application: `Application.components` (public since M8) exposes the
kernel's event bus, and the CLI's `CommandProcessor` wires the observer
whenever the Application is started and detaches it when stopped. The
Application layer has **zero diffs** this milestone; so do runtime,
scheduler, decision engine, learning, repositories, domain, api,
infrastructure, daemon, and dashboard.

Two design consequences of observing a **synchronous** bus (M3: handler
exceptions propagate to the publisher):

- Every manager handler is exception-tight — a formatting surprise or a
  failing provider can never break a kernel broadcast (tested with
  malformed payloads and a provider that throws).
- Attachment happens after `Application.start()` (the bus is built
  during start), so KernelBooted has already been broadcast when the
  observer is born; `attach(bus, started_at=...)` therefore records the
  ApplicationStarted notification itself. KernelShutdown IS observed
  live during `stop`.

## 2. Supported events (mission -> bus vocabulary)

| Mission event | Bus signal observed | Notification |
| --- | --- | --- |
| RecommendationGenerated | `RECOMMENDATION_GENERATED` | the recommendation's reason ("Study ISTQB for 60 minutes" style) |
| RecommendationAccepted | `PLAN_UPDATED` (updated rec status Accepted) | "Recommendation accepted: …" |
| RecommendationRejected | `PLAN_UPDATED` (status Rejected) | "Recommendation rejected: …" |
| EventStarted / Paused / Resumed / Cancelled | `EVENT_STATE_CHANGED` (event status) | "Started/Paused/Resumed/Cancelled: {description}" |
| EventCompleted | `EVENT_STATE_CHANGED` (Completed) | "{description} completed" ("Deep work completed") |
| — the "time to start" reminder | `EVENT_STATE_CHANGED` (Ready) | "Time to start {description}" |
| ContextChanged | `RUNNING_CONTEXT_CHANGED` | "Context changed (window …)" |
| DisturbanceDetected | `DISTURBANCE_DETECTED` | "Unexpected interruption recorded: …" — **Critical** when severity is High |
| TimeProgressed | `TIME_PROGRESSED` | "Time progressed" (Info; cooldown-throttled) |
| LearningCompleted | `INSIGHT_GENERATED`, `REFLECTION_CREATED`, `HABIT_DETECTED` | "New insight generated" / "Reflection recorded" / "New habit detected" |
| ApplicationStarted | `KERNEL_BOOTED` + attach-time announce | "Application started" |
| ApplicationStopped | `KERNEL_SHUTDOWN` | "Application stopped" |

Bookkeeping states (Recommended/Scheduled/Archived, Consumed/Expired
recommendation churn) are deliberately silent. Payload entities are
read duck-typed (the CLI/TUI/API serialization convention) and never
mutated or called. The "Lunch overdue" reminder rule has no publisher
in the current vocabulary — an overdue signal would have to be
*computed*, which an observer must not do; the Ready→"Time to start"
reminder covers the published reality, and an overdue event type is
listed in the roadmap.

## 3. Provider model

`NotificationProvider` (ABC): `name` + `send(notification)`. Providers
are transport only — the manager has already formatted, deduplicated,
and quiet-filtered. A provider failure raises `ProviderError`; the
manager isolates it so remaining channels still deliver.

- **ConsoleProvider** — one line per notification on a text stream
  (`- [HH:MM] [Category] message`, `!` marker for Critical).
- **DesktopProvider** — Qt system-tray toasts. PySide6 stays the GUI
  tier's dependency: imported lazily, only here; without PySide6, a
  QApplication, or a system tray it raises `ProviderUnavailableError`
  at construction. An injectable notifier callable decouples it from Qt
  entirely (the GUI and the tests use that seam).
- **NullProvider** — the silent sink; history still records.

## 4. History model

`NotificationHistory`: an in-memory ring buffer (default 200), newest
first, per-notification `read` flag, `unread_count`, `mark_all_read()`,
`clear()`. **No persistence** — the observer owns no files; a restart
starts an empty history (audit rule, enforced by AST test).

## 5. Deduplication

Identity is `category:message`. A notification identical to one already
sent within `cooldown_seconds` (default 300) is dropped entirely —
neither routed nor recorded (a duplicate in history would be its own
kind of spam). Sent-time bookkeeping uses the event's `occurred_at`, so
behaviour is deterministic under the ManualClock. This also throttles
the per-tick `TimeProgressed` heartbeat to one notice per cooldown.

## 6. Quiet hours

`QuietHours(start, end)` supports same-day and midnight-crossing
windows (the mission's 22:00–07:00) with `parse("22:00-07:00")`.
During quiet hours non-critical notifications are **held**: recorded in
history unread (visible next morning, counted by `notifications
unread`) but not routed to providers. **Critical** notifications
(high-severity disturbances) bypass quiet hours. Configurable via
`NotificationConfig` and the CLI's `--quiet-hours HH:MM-HH:MM` option.

## 7. Desktop GUI integration (M13)

The GUI is REST-only and imports nothing from `paios` (M13 hard rule,
still AST-enforced), and this milestone's stop condition forbids REST
changes — so the GUI's center observes the only stream it has:
successive `/dashboard` polls.

- `paios_gui/notifications.py` — Qt-free: `NotificationCenter`
  (bounded, newest-first, unread tracking) and `DashboardWatcher`,
  which diffs consecutive payloads (new recommendation ids, new
  disturbers, running-event change, execution-context change) into
  notifications. The first observation is a silent baseline.
- **Notification center page** — new nav entry between History and
  Settings: history table (unread marker, time, category, message),
  "Mark all read", "Clear".
- **Unread count** — a live badge on the nav entry:
  "Notifications (3)".
- **Desktop notifications** — a `QSystemTrayIcon` toast per watcher
  finding (Critical icon for high-severity disturbances); skipped
  gracefully where no tray exists (headless test runs).
- `/dashboard` is now fetched on every poll regardless of the visible
  page, so news is noticed anywhere; action feedback (`notify`) also
  lands in the center.

## 8. CLI

| Command | Behaviour |
| --- | --- |
| `notifications` | List unread and mark them read |
| `notifications history` | List everything retained (`*` = unread) |
| `notifications unread` | Unread count |
| `notifications clear` | Empty the history |

Wiring: `paios shell` narrates through a ConsoleProvider on the shell's
stream; one-shot runs use the NullProvider (their output contract
predates M14) while still recording in-process. `--quiet-hours` is a
global CLI option. The `CommandProcessor` keeps the observer attached
exactly while the Application is started — across `start`/`stop`
cycles in one shell session.

## 9. Tests

55 new tests; full suite **751 passed, 1 skipped** (697 regression
intact). The skip is the DesktopProvider "no QApplication" guard test,
which cannot run after the GUI suite has created the process-wide
QApplication; the guard's logic is otherwise covered.

- **Routing** — every supported event through a real EventBus; message
  and category per rule; accepted/rejected discrimination; silent
  bookkeeping states; severity mapping.
- **Observer contract** — malformed payloads never raise into the
  publisher; failing provider isolated; detach stops observing; attach
  idempotent; the manager never publishes (recording-bus proof); the
  manager's collaborators are exactly bus/providers/history.
- **Deduplication** — inside/at/after the cooldown boundary; distinct
  messages unaffected; duplicates never reach history.
- **Quiet hours** — midnight-crossing and same-day windows; held
  notifications recorded unread; Critical bypasses; parse errors.
- **History** — unread count, mark-all-read, newest-first, clear, ring
  limit.
- **Providers** — ABC contract enforced; Null silent; Console format +
  Critical marker + broken-stream error; Desktop via injected notifier
  and the unavailable guard.
- **Application integration** — over a real seeded Application: tick →
  recommendation notification; accept/start/complete flow; disturber →
  Critical; stop → ApplicationStopped; and a proof the observed
  Application behaves exactly as unobserved.
- **CLI** — full shell flow for all four commands, console narration,
  quiet-hours option (held from console, counted unread), invalid
  option error, one-shot behaviour, help listing.
- **Desktop integration** — center model; watcher baseline/diff cases;
  window: badge updates, page lists/marks/clears, REST-driven event
  start noticed, action feedback recorded. Rendered screenshots
  verified visually (center page with badge and unread rows).
- **Forbidden imports** — AST: the package may import only stdlib, its
  own modules, and the bus vocabulary; Qt only inside the desktop
  provider; no persistence modules; no `open()`.

## 10. Audit

| Check | Result |
| --- | --- |
| No Runtime mutations | PASS — zero diffs in `paios/runtime`; the manager holds no kernel reference (asserted) and only reads payloads. |
| No Scheduler mutations | PASS — zero diffs; no import (AST-enforced). |
| No Decision Engine mutations | PASS — same. |
| No Learning mutations | PASS — same; LearningCompleted subscribes to the reserved vocabulary rather than adding publishers. |
| Observer only | PASS — subscribe-only bus use (recording-bus test), exception-tight handlers, unobserved-vs-observed behaviour identical. |
| Application layer untouched | PASS — zero diffs in `paios/application`; attachment lives in the CLI composition root via the public `components` property. |
| REST unchanged (stop condition) | PASS — zero diffs in `paios/api`; the GUI center feeds on existing polls. |

## 11. Future roadmap

- **Provider registry + config file** — providers are hard-wired at
  composition roots; a small registry keyed by name would let users
  enable channels declaratively (Android/Discord/Email/Push slot in as
  `NotificationProvider` implementations).
- **Overdue reminders** — "Lunch overdue" needs an `EVENT_OVERDUE`
  publisher (Scheduler vocabulary); once published, one routing entry
  here delivers it.
- **REST exposure** — `GET /notifications` (+ mark-read/clear) would
  let the GUI show the *backend's* history instead of its poll-derived
  one; deferred because this milestone forbids REST changes.
- **Persistent history** — an opt-in store if notification history
  should survive restarts; deliberately absent now (observer owns no
  files).
- **Async delivery** — slow future channels (email, push) need a queue
  so the synchronous bus never waits on a network; today's channels are
  instant.
- **Daemon integration** — the M9 daemon could attach a manager the
  same way the CLI does, giving continuous background notification.

## 12. Suggested commit message

```
Milestone 14: Notification system - Event Bus observer with providers

- paios.notifications: NotificationManager subscribes to the System
  Event Bus, formats the mission's rules, deduplicates (cooldown),
  applies quiet hours (Critical bypasses), routes to providers, keeps
  an in-memory unread-aware history; exception-tight observer
- Providers: ConsoleProvider, DesktopProvider (Qt tray, lazy optional
  import, injectable notifier), NullProvider behind a small ABC
- CLI: notifications / history / unread / clear; --quiet-hours option;
  shell narrates via ConsoleProvider; observer attached by the
  composition root exactly while the app is started
- GUI (M13): notification center page, nav unread badge, tray toasts,
  poll-diff watcher over /dashboard (REST unchanged)
- Zero diffs in application/runtime/scheduler/decision-engine/learning/
  repositories/domain/api; AST-enforced import boundaries
- Tests: 55 new (routing, dedup, quiet hours, history, providers,
  application integration, CLI, GUI); suite 751 green + 1 guard skip
```

## Stop condition

Milestone 14 ends here. No AI assistant, chat, voice, Android, plugin
system, or REST changes have been started. Awaiting review.
