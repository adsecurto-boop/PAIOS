# Changelog

All notable changes to PAIOS. Versions follow semantic versioning; the
version in `pyproject.toml` / `paios.__version__` is the source of truth
and is what GitHub Release tags must match (`v<version>`).

## [Unreleased] — Connection reliability & first-run readability

### Fixed
- **False "Offline" on Test Connection.** A model round trip legitimately
  takes tens of seconds (the Ollama adapter allows 300 s), but both the
  desktop Test AI and the mobile Test Connection made the call under the
  short polling deadline (2 s desktop / 5 s mobile) and rendered every
  timeout as "server unreachable". AI-bearing calls now carry their own
  deadline (`AI_REQUEST_TIMEOUT_SECONDS`), and timeouts are a distinct
  error (`ApiTimeout` / `ApiTimeoutException`, a subtype of unreachable)
  that the UI reports as "still loading", never as offline.
- **The API server serialized all requests behind one accept loop.** A
  single in-flight model call blocked every poll, so a healthy backend
  looked offline to both the desktop and the phone. The transport is now
  a `ThreadingHTTPServer`; provider-only routes
  (`routes.CONCURRENT_PATHS`) run outside a new process-wide domain lock,
  while every route that touches the store or kernel stays serialized
  behind it (per-request context moved to thread-local).
- **Mobile "Save server" did nothing visible.** The button now
  validates the address, shows "Saving…", persists unconditionally
  (settings survive an unreachable desktop), re-checks the connection,
  and reports the outcome — inline and as a snackbar.
- **Mobile Test Connection replaced with a staged check**
  (`connection_check.dart`): desktop → pairing → desktop AI, naming the
  link that broke instead of a blanket "Offline". The phone still asks
  the desktop for AI answers and never contacts Ollama directly.
- **Mobile LAN probe mis-normalized the address**, so a reachable
  desktop entered as `host:port` or with a trailing slash was classified
  unreachable. The probe now normalizes exactly like `ApiClient`.
- **First-run readability.** The desktop wizard pinned every surface it
  owns to the app palette, and both themes now define a WCAG-AA disabled
  text colour (Qt's derived grey was unreadable on the wizard's disabled
  controls). The Android launch/normal window and splash use the app's
  own dark surface, removing the white flash on cold start.

### Changed
- Desktop Test AI now walks the chain in two stages (backend, then
  provider) with the AI deadline on the provider call and each stage
  painted before it blocks; the Intelligence page's four-call refresh is
  throttled off the poll cadence, which was the actual per-poll UI cost.
- Mobile polling is re-entrancy-guarded and skips re-encoding an
  unchanged dashboard; the app root rebuilds on theme change only, not on
  every poll tick.
- Every API request is logged in full (method, path, headers, body,
  status, response, tracebacks) with credentials redacted; nothing is
  swallowed.

## [2.4.0] — 2026-07-23 — Milestones 21–25 "AI, Networking, Remote Access, Desktop & Mobile"

### Added — Milestone 21 "AI & Networking"
- Intelligence page (desktop): Intelligence Mode selector (Automatic /
  Local AI / OpenAI / Anthropic / Offline), automatic Ollama detection,
  installed-model dropdown, one-click "Use Local AI" (installs the
  recommended model when needed), a Test AI button that reports the
  round-trip latency, hardware and model info, and a green/yellow/red
  status light. No config files or environment variables to edit.
- Networking page (desktop): live hostname / LAN IP / port / Wi-Fi /
  server / firewall status; Start · Stop · Restart the API; a
  Local Only ↔ Local Network access toggle; copy-address and QR-code
  for phone pairing; and a one-click Windows firewall helper. Every
  action happens in the GUI — no terminal, ever.
- Persisted network access mode (`network-settings.json`): the API
  binds loopback-only by default and to all interfaces only after the
  user chooses Local Network; `paios serve` and the product launcher
  honour the choice on (re)start, so a paired phone can reach PAIOS
  over the same Wi-Fi without any manual configuration.
- REST: `GET/PUT /system/network`, `POST /system/network/firewall`,
  `GET /system/server` (facts + mode toggle + firewall + status;
  mutations are loopback-only, like pairing administration).
- Pairing page: the generated code now shows a QR of the connection
  address and a live five-minute expiry countdown.
- QR codes via the pure-Python `segno` library (GUI tier only; bundled
  into the frozen product — the backend stays dependency-free).

### Added — Milestone 22 "Automatic LAN discovery"
- mDNS / DNS-SD advertising (`backend/paios/system/discovery.py`, pure
  stdlib): in Local Network mode the desktop advertises `_paios._tcp`
  so a phone on the same Wi-Fi discovers it with no typed IP. Started
  and stopped with the API server; best-effort and loopback-safe.
- REST `GET /system/discovery` and a `discovering` flag on
  `/system/network`; a "Discoverable on Wi-Fi" chip on the Networking
  page.

### Added — Intelligence enhancements
- Model details over Ollama's `/api/show` (`POST /assistant/ollama/show`):
  context length, parameter size and quantization, shown on the
  Intelligence page.
- A GPU/CPU indicator chip (uses the existing hardware detection).

### Added — Milestone 23 "Remote access" (relay core)
- Portable, self-hostable relay (`relay/`, stdlib-only, imports nothing
  from PAIOS): a reverse-tunnel broker so a phone reaches its desktop
  from any network without exposing the desktop. Run it with
  `python relay.py` or `docker compose up -d` on any host (Oracle Cloud,
  Raspberry Pi, DigitalOcean, Hetzner, AWS, Azure) with no code changes.
  - HS256 JWT access tokens + rotating refresh tokens, bound to one
    account and device; a phone gets a token only after the desktop
    authorizes its paired device; nonce+timestamp replay protection;
    constant-time desktop credential check; optional direct TLS or
    reverse-proxy termination. Dockerfile + docker-compose + README.
- Desktop connector (`backend/paios/system/relay_client.py`): dials out
  and long-polls the relay (also the heartbeat), forwards each phone
  request to the local API carrying the phone's own device auth end to
  end, posts the response back, and reconnects with capped backoff.
- Desktop integration: `relay-settings.json` (account key DPAPI-protected
  like the cloud keys), the connector started/stopped with the server and
  reconfigured live, `GET`/`PUT /system/relay` (loopback-only mutations),
  a "Remote access" section on the Networking page (enable, relay address,
  account, key, live status chip), and a pairing→relay-authorize bridge so
  a phone paired on Wi-Fi immediately works remotely. The pairing QR now
  encodes a versioned `paios://pair` payload carrying LAN + relay
  endpoints for the phone's LAN→Relay→Offline auto-selection.

### Added — Milestone 24 "Desktop UX polish"
- Dual themes: a refined **dark** and a first-class **light** theme,
  switchable live from Settings and persisted; the first-run wizard now
  offers both. One stylesheet builder and semantic status palette keep
  every page consistent (rounded cards, roomier spacing, hover/focus
  states, tooltips).
- Discoverability: a keyboard-shortcuts dialog (**F1**), plus new
  shortcuts (**Ctrl+,** Settings) and tooltips on the core controls.
- Accessibility: accessible names on the navigation, search and key
  inputs.

### Added — Milestone 25 "Mobile remote connectivity"
- The phone auto-selects **LAN → Relay → Offline** with no user action,
  wired into the live poll loop (`ConnectionManager` in `AppState`): a
  fast LAN probe first, then the relay when off-network, then offline
  (cache + queue); a dropped LAN switches to the relay on the next poll.
  An on-screen indicator shows the mode in plain language ("Connected
  from anywhere"), and the Settings screen carries a "Use PAIOS
  anywhere" card (relay address + paste-a-connection-code auto-fill).
- `RelayHttpClient` wraps every request in the relay envelope
  transparently, so the entire existing app works over mobile data with
  no per-screen changes — JWT auth with automatic refresh + replay-safe
  nonces.
- Pairing payload parser reads the desktop's `paios://pair` QR (LAN +
  relay + account) or a plain address.
- Verified end to end on the now-working Flutter toolchain:
  `flutter analyze` clean, `flutter test` 89 passing, and a **release
  APK** (`app-release.apk`) builds successfully.

### Packaging — Milestone 26
- Rebuilt production artifacts at this version: `PAIOSSetup.exe`,
  `PAIOSUpdater.exe`, `PAIOSUninstall.exe` (Inno Setup; `segno` bundled;
  `SHA256SUMS.txt` + `RELEASE_NOTES.md`), and the mobile **release APK**
  (v1.1.0). Backend 1336 tests + 1 skipped green; mobile 96 tests green.

### Non-technical-user guarantee
- After installation, using local AI and connecting the Android app
  require no Command Prompt, PowerShell, environment variables,
  configuration files, or manual networking — everything is in the GUI.

## [2.2.0] — 2026-07-22 — Milestone 20 "Product Polish & Daily Planning"

### Added
- Planning module (`backend/paios/planning/`): Inbox, Event Templates,
  Recurrences, Event Metadata sidecar (tags/deadline/energy/duration/
  dependencies), Planning Proposals and intent processing.
- User-authored events: intents ride the existing Recommendation →
  Scheduler materialization pipeline (Scheduler remains the only
  scheduling authority).
- Additive Application façade methods: `propose_user_event`,
  `edit_event`, `duplicate_event`, `plan()`.
- REST: `POST /events`, `PUT /events/{id}`, `POST /events/{id}/duplicate`,
  `/events/{id}/metadata`, `GET /plan`, `/templates`, `/recurrences`,
  `/inbox`, `/assistant/*`, `/backups`.
- AI Assistant wired to REST (proposal + explanation only, never mutation):
  capture classification and day-plan explanation tasks.
- Desktop: Planning landing page, Inbox, full Event Manager, interactive
  Timeline (Today/Tomorrow/Week/Agenda), search, log viewer, backup
  manager, first-run wizard, expanded shortcuts, dashboard polish.
- Mobile: planning/inbox/timeline screens, FAB, swipe actions, offline
  cache, Material 3 polish, adaptive layouts.
- Auto-update: standalone `PAIOSUpdater.exe` (GitHub Releases, semver,
  SHA256 verify, backup/rollback) + periodic update checks in PAIOS.exe.
- Release hygiene: version single-sourced (2.2.0), SHA256 checksum and
  release-notes emission in the installer build.

### Unsupported by design
- Hard event deletion (Domain records evidence; Archive is the removal UX).
- Drag-and-drop rescheduling (the Scheduler is the sole scheduling
  authority and rebuilds the plan each cycle).

## [2.1.0] — 2026-07-22 — Milestone 19 "Productization"

- Product launcher (`PAIOS.exe`): process supervision of daemon + API +
  GUI, system tray with status, single-instance guard, crash reports.
- Windows installer (`PAIOSSetup.exe`): venv layout, wheel install,
  shortcuts, HKCU Run registration, optional logon task, uninstaller.
- PyInstaller build pipeline (`scripts/build_installer.py`).

## [2.0.0] — 2026-07-22 — Milestones 13–18

- Native desktop dashboard (PySide6, REST-only).
- Mobile companion app (Flutter, REST-only).
- AI Assistant package (explain/summarize tasks; Anthropic/OpenAI/Null
  adapters).
- Deployment tooling, backups, system config, notifications.
- Production readiness audit (858 tests passing).

## [1.0.0] — 2026-07-21 — Milestones 10–12

- Terminal dashboard and read-only monitoring interface.
- REST API over the Application façade (`paios serve`).
- CLI shell (`paios shell`).

## [0.9.0] — 2026-07-21 — Milestone 9

- Runtime daemon / timer engine: drift-free continuous execution.

## [0.5.0] — 2026-07-21 — Milestones 4–8 (tag `architecture-consistent-v0.5`)

- Scheduler, Decision Engine, Application layer, Learning Engine, ADR-003
  consistency resolution.

## [0.1.0] — 2026-07-20 — Milestones 1–2

- Frozen Domain layer (12-state Event lifecycle, one Event aggregate).
- Repository layer with aggregate reconstitution (JSON persistence).
