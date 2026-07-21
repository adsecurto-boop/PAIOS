# Milestone 15 — Mobile Companion (Flutter)

## Mission

The first mobile client for PAIOS. The phone is only a client: the
laptop remains the operating system; the phone never schedules, learns,
reasons, or stores domain state. Everything flows through the REST API.

## 1. Architecture analysis (Phase 1 outcome)

Canonical documents, all three ADRs, all implementation reports
(M1–M14), and the codebase were reviewed. One contradiction was found
and resolved through the mandatory stop-and-approve path:

- **Approved additive correction** — the mission's Events screen
  requires *Archive*, which existed in the Application facade and CLI
  but not over HTTP. The approved endpoint was added exactly as
  specified: `POST /events/{id}/archive` → one delegation to
  `Application.archive_event(EventId(id))` → `200 {"result":
  "archived"}`, mechanically identical to the other event action routes
  ([routes.py](../../backend/paios/api/routes.py)). Two endpoint tests
  were added (archive after completion → `Archived`; archiving a
  running event → translated error, not a crash). **No other backend
  modification**; full backend suite: **753 passed, 1 skipped**.
- No frozen-layer modification beyond that: the app is a new tier at
  `frontend/mobile/`, exactly parallel to M13's desktop GUI.
- The Notifications screen deliberately mirrors M14's approved pattern
  (dashboard-diff watcher, client-side center) — **no backend
  notification endpoint**, as the mission mandates.

```
Phone (Flutter, Dart — imports nothing from the backend, by language)
  └── ApiClient (package:http; the ONLY networking module)
        ↓ HTTP (LAN)
      REST API → Application → Runtime → Scheduler → Decision Engine → Learning
```

## 2. Project layout (the mission's folder contract)

```
frontend/mobile/
  pubspec.yaml            flutter + http + shared_preferences only
  lib/
    main.dart             app shell: drawer nav (10 screens), unread badge
    theme/app_theme.dart  Material 3, dark-first (light optional)
    models/models.dart    typed views over M12 payloads; parsing only
    services/
      api_client.dart     one method per endpoint; two failure types
      settings_service.dart  preferences (URL, interval, theme) + caches
      notification_center.dart  center + DashboardWatcher (pure Dart)
      app_state.dart      presentation state: snapshot, online flag,
                          poll timer, notification center, actions
    screens/              dashboard, recommendations, events, goals,
                          projects, contexts, resources, reflections,
                          notifications, settings (+ shared REST list base)
    widgets/              SectionCard, OfflineBanner
  test/                   see §6
```

Platform scaffolding (`android/` etc.) is generated locally with
`flutter create --platforms=android .` (see the README, including the
Android cleartext-HTTP note for plain-http LAN use) — the repo tracks
source and tests, not generated boilerplate.

## 3. Screens and REST usage

| Screen | Reads | Actions (one endpoint each) |
| --- | --- | --- |
| Dashboard | `GET /dashboard` + `GET /resources` | — (pull-to-refresh + auto-refresh) |
| Recommendations | `GET /recommendations` | accept, reject (optional reason) |
| Events | `GET /events` | start, pause, resume, complete (optional outcome), **archive** |
| Goals / Projects / Contexts / Resources / Reflections | their list endpoints | read-only |
| Notifications | local center (M14 mirror) | mark read, clear (local) |
| Settings | — | preferences only |

Dashboard cards mirror the desktop: Time, Status, Current Event
(elapsed/remaining), Current Context, Goals, Projects, Recommendations,
Health (+ today's counts), Resources, Learning, Recent Reflection,
Notifications. Auto-refresh runs on a configurable timer; pull-to-
refresh via `RefreshIndicator`.

The server URL is **never hardcoded**: it lives in preferences, is
editable in Settings (default placeholder `http://192.168.1.15:8765`),
and swapping it rebuilds the client and re-polls immediately.

## 4. Offline behaviour

- Every failure path funnels into two exception types; `refresh()` and
  `runAction()` never throw — the mission's "never crash".
- On failure: `online=false`, a persistent OFFLINE strip appears, the
  **last successful snapshot stays on screen**, and the poll timer *is*
  the retry (automatic).
- The last dashboard JSON is cached in preferences: a fresh app start
  with the laptop unreachable still renders the previous snapshot.
- Reconnecting flips the banner and logs "Connected" to the center.

Local persistence is exactly the three permitted stores: preferences,
cached dashboard, notification history (which round-trips through JSON
so read-state survives restarts). Nothing else touches storage.

## 5. Notifications (M14 mirror)

`DashboardWatcher` diffs consecutive `/dashboard` snapshots — new
recommendation ids, new disturbers (High → error kind), running-event
change, execution-context change; the first observation is a silent
baseline. The center is bounded, newest-first, unread-tracked; the
AppBar bell and the drawer entry carry the unread badge; the screen
offers Mark-all-read and Clear. Pure presentation diffing of ids the
API already sent — no business logic, no backend endpoint.

## 6. Testing

Authored per the mission's five categories (run with `flutter test`
from `frontend/mobile/`; goldens seeded once with
`flutter test --update-goldens test/golden_test.dart`):

- **REST client tests** (`api_client_test.dart`) — against a real
  in-process `dart:io` HttpServer: envelope unwrapping, every event
  action including archive hits exactly one endpoint (asserted from the
  server's request log), accept/reject, API error payload → typed
  exception (status + type + message), unreachable → `ApiUnreachable`,
  bare-host URL normalization.
- **Mock server tests** (`widget_test.dart` + `MockClient`) — the shell
  over canned REST: every dashboard card renders, drawer reaches every
  screen, Events → Archive issues `POST /events/e1/archive` and nothing
  else, Accept issues its single endpoint, notifications mark/clear,
  Settings edits the server URL and rebuilds the client.
- **Offline tests** (`offline_test.dart`) — disconnection keeps the
  snapshot and flips the banner state; cached dashboard renders on an
  offline boot; reconnect recovers and logs; notification history
  (incl. read state) survives an app restart.
- **Widget tests** — as above, plus model parsing
  (`models_test.dart`: full payload, empty payload, running event) and
  the watcher/center suite (`notification_center_test.dart`).
- **Golden screenshots** (`golden_test.dart`) — dark dashboard and the
  offline-banner state at phone dimensions.

**Environment caveat (honest):** per the milestone instruction, no
Flutter/Dart SDK was installed in this environment, so the Dart suites
were authored but not executed here. What *was* executed: the full
backend suite (753 passed, 1 skipped) including the two new archive
endpoint tests — the REST contract the app consumes is verified
server-side. The Dart code sticks to long-stable APIs (one
version-sensitive construct, `CardTheme`, was deliberately dropped).
First `flutter test` run on a machine with the SDK is the remaining
verification step.

## 7. Audit

| Check | Result |
| --- | --- |
| No business logic | PASS — models parse, screens render, actions delegate; the only client-side derivations are display formatting and the M14-approved id-diffing. |
| No domain logic / scheduler / runtime / learning | PASS — the phone has no such code; Dart cannot import the Python backend, and no logic was reimplemented. |
| REST only | PASS — `api_client.dart` is the single networking module; every path it references exists in the API route table (mechanically compared); `dart:io` appears only for socket exception types. |
| No domain state on device | PASS — storage is exactly preferences + cached dashboard + notification history. |
| Frontend imports nothing from backend | PASS — dependencies are flutter, http, shared_preferences. |
| Backend untouched beyond the approved correction | PASS — diff is `routes.py` (+9 lines) and `tests/api/test_endpoints.py`. |

## 8. Future roadmap

- **Run `flutter test` in CI** — a GitHub Action with the Flutter SDK
  would close the environment caveat permanently and gate goldens.
- **TLS + authentication** — mission-excluded here; prerequisites for
  leaving the trusted LAN (the cleartext-HTTP manifest note goes away
  with it).
- **Server-sent events** — polling matches the desktop; an SSE feed
  would cut latency and battery cost without websockets.
- **Write actions parity** — goal/project creation, progress,
  reflections and disturber reporting exist over REST; mobile forms are
  a mechanical addition when wanted.
- **Push notifications** — the M14 provider roadmap's Android channel;
  needs a delivery service, deliberately out of scope.

## 9. Suggested commit message

```
Milestone 15: Mobile companion - Flutter REST client

- frontend/mobile: Material 3 dark-first Flutter app; drawer nav over
  10 screens; dashboard mirrors the desktop cards with auto refresh
  and pull-to-refresh
- REST-only: single ApiClient (http package); configurable server URL
  in Settings (never hardcoded); one endpoint per action including the
  approved POST /events/{id}/archive
- Offline: last snapshot cached and rendered, OFFLINE banner, poll
  timer as automatic retry, never crashes
- Notifications: M14 mirror - dashboard-diff watcher, unread badge,
  history persisted locally, mark read / clear; no backend endpoint
- Approved backend correction: POST /events/{id}/archive (one facade
  delegation) + 2 endpoint tests; no other backend changes; backend
  suite 753 green
- Tests: models, watcher/center, REST client vs dart:io mock server,
  widget + mock server, offline, goldens (flutter test)
```

## Stop condition

Milestone 15 ends here. No AI assistant, authentication, cloud sync,
plugin, timer, or desktop work has been started. Awaiting review.
