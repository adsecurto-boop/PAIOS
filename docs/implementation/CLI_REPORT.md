# CLI Report — Milestone 7

The first Human Interface for PAIOS: a plain-text command-line layer that
parses, validates, routes, formats, and delegates. Every command performs
exactly one primary delegation into the Application facade; the CLI edits
nothing, decides nothing, persists nothing.

Status: complete, audited, **448 tests passing** (137 domain + 65
repository + 60 runtime + 54 scheduler + 33 decision engine + 52
application + 47 CLI). All frozen layers byte-untouched — Milestone 7
added only `backend/paios/cli/` and `tests/cli/`.

## 1. Architecture

```
User ──► CLI ──► Application ──► Runtime ──► Scheduler ──► Decision Engine
                     │                                          │
                     └────────────► Repositories ◄──────────────┘
CLI imports: paios.application + the facade's own signature vocabulary
(domain identifiers, DisturberType/Severity) + stdlib. NOTHING ELSE —
grep-verified. Debug commands reach internals exclusively through the
facade's sanctioned `components` property via attribute access (no
imports), and the formatter is duck-typed over facade outputs.
```

Two interpretation decisions, made openly in Phase 1:

- **`reflect` is read-only.** Reflection *capture* needs an Application
  use case that belongs to the deferred Learning layer; adding one would
  modify frozen Milestone 6. The command lists persisted Reflections.
- **"Exactly one Application method"** = one primary delegation. Resolving
  a typed ordinal (`accept 1`) to an identifier uses read-only queries —
  input validation, not a second action.

## 2. Folder Structure and Responsibilities

```
backend/paios/cli/
├── __init__.py       exports
├── exceptions.py     CliError → UnknownCommandError, CommandArgumentError
├── parser.py         CommandSpec registry (name, usage, arity, help);
│                     parse_line: syntax validation only, no meanings
├── formatter.py      ALL presentation: clean text, no JSON, no ANSI
├── commands.py       CommandProcessor: routing + one delegation per
│                     command + ordinal/ID resolution helpers
├── interactive.py    Shell: line REPL over injectable streams; survives
│                     every error; exit/quit
└── main.py           entry point: --data-dir option, one-shot mode
                      (auto-start/auto-stop around the command), shell mode
```

## 3. Command Reference

| Command | Delegation |
|---|---|
| `paios start` / `stop` | `Application.start()` / `stop()` |
| `paios status` | `status()` |
| `paios snapshot` | `snapshot()` |
| `paios tick` | `tick()` — one runtime loop pass |
| `paios recommendations` | `active_recommendations()` (numbered) |
| `paios accept <ref>` / `reject <ref>` | `accept_recommendation()` / `reject_recommendation()` — `<ref>` is a listing number or a raw ID |
| `paios events` / `event <ref>` | `snapshot()` → listing / detail |
| `paios start-event / pause-event / resume-event / cancel-event <ref>` | the matching facade method |
| `paios complete-event <ref> [text...]` | `complete_event(actual_outcome=text)` |
| `paios context` | `snapshot()` → execution context, active window, known Contexts |
| `paios projects` | `snapshot()` → projects with completion |
| `paios reflect` | `snapshot()` → Reflections (read-only; see §1) |
| `paios disturb <type> <severity> <description...>` | `report_disturber()` (user derived from snapshot aggregates, fallback `user_001`) |
| `paios debug runtime\|scheduler\|kernel\|bus` | facade surfaces / `components` (attribute access only) |
| `paios help [command]`, `paios shell` | help system / interactive mode |

## 4. Formatter Examples

```
> status
State:             Running
Operational:       yes
Booted at:         2026-07-21 09:00
Execution context: IdleExecutionContext (Waiting) since 2026-07-21 09:00
Services:          clock, event_bus, snapshot_manager, invariant_checker, scheduler
Latest snapshot:   2026-07-21 09:00
Aggregates:        contexts=1, principles=1, resources=1

> recommendations
Active recommendations:
1. [Pending] Energy is low (10 points); rest to recover
   priority 8.5 | confidence 0.85 | expires 2026-07-21 10:00

> tick
1 recommendation(s):
1. Energy is low (10 points); rest to recover (priority 8.5, confidence High)
   why: Energy is low (10 points); rest to recover
   principles: Protect Health

> event 1
Event:        3f0e...-....
Description:  Energy is low (10 points); rest to recover
Status:       Completed
Transitions:  Scheduled -> Ready -> Started -> Completed
```

## 5. Interactive Mode

```
$ paios shell
PAIOS interactive shell. Type 'help' or 'exit'.
> start
PAIOS started.
> tick
1 recommendation(s): ...
> accept 1
Recommendation accepted.
> start-event 1
Event started.
> complete-event 1 rested well
Event completed.
> exit
Goodbye.
```

Errors never kill the shell: CLI errors and application/domain errors are
printed as one-line messages and the prompt returns.

## 6. Tests — 47 new

- `test_parser.py` (10) — parsing, arity + usage errors, blank input,
  unknown commands, the full mission command registry.
- `test_commands_and_formatter.py` (25) — **delegation proven with a
  recording fake** (each command → exactly one primary facade call;
  ordinal resolution; free-text outcome pass-through; out-of-range guards);
  real end-to-end golden path (tick → accept 1 → start-event 1 →
  complete-event 1 → detail); reject; context/projects/reflect; disturb
  incl. enum validation; all four debug targets; formatter qualities (no
  ANSI, no JSON, full help, per-command help).
- `test_shell_and_main.py` (12) — the scripted mission session; invalid
  commands and application errors keeping the shell alive; blank lines;
  quit/EOF; main: help default, one-shot auto-start/auto-stop, clean
  failure exit codes, shell mode via main.

## 7. Audit

| Check | Result |
|---|---|
| CLI imports Application only (+ signature vocabulary) | grep: `paios.application`, `paios.domain.enums`, `paios.domain.value_objects.identifiers`, `paios.cli.*`, stdlib — nothing else |
| Never imports Runtime / Scheduler / Decision Engine / Repositories | zero matches |
| Never mutates domain entities / runtime state / repositories / snapshots | zero calls to any transition, admission, persistence, or execution-context API |
| Every command delegates | proven per-command with the recording fake |
| Zero duplicated logic | formatting is presentation; resolution is validation; everything else is a facade call |
| No clock access | zero `datetime.now`; the codebase total remains the one sanctioned Clock site |
| Frozen milestones untouched | only `paios/cli/` + `tests/cli/` added; prior 401 tests pass unchanged |

## 8. Future CLI Roadmap

- **Reflection capture** (`reflect <event-ref> ...`) once the Learning
  layer adds the Application use case.
- ANSI colour and width-aware tables (explicitly excluded this milestone).
- A resident daemon / IPC mode so one-shot commands can address a running
  PAIOS instead of auto-start/auto-stop per process (pairs naturally with
  the future Timer Engine driving `tick` autonomously).
- Command history and completion in the shell.
- `--user` selection when multi-user composition arrives.
- Context creation/editing commands once a capture flow is specified.

## 9. Suggested Git Commit

```
Milestone 7: CLI - first human interface, delegation-only

- parser (spec registry, arity/usage validation), formatter (all
  presentation, plain text), CommandProcessor (one primary delegation per
  command, ordinal/ID resolution), interactive shell, main entry with
  one-shot auto-start/stop and shell mode
- Full mission command set incl. disturb, debug targets, help system
- reflect is read-only by design (Learning-layer capture deferred)
- 47 new tests incl. recording-fake delegation proofs and a scripted
  shell session; 448 total passing; frozen layers untouched

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
```

---

Milestone 7 deliverables complete. No Dashboard, GUI, API, or AI chat work
will begin without explicit approval.
