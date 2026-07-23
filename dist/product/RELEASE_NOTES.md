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

### Added — Milestone 25 "Mobile remote connectivity" (core)
- The phone auto-selects **LAN → Relay → Offline** with no user action
  (`connection_manager.dart`): a fast LAN probe first, then the relay
  when off-network, then offline (cache + queue). Modes surface in plain
  language ("On your Wi-Fi", "Connected from anywhere", "Offline").
- `RelayHttpClient` wraps every request in the relay envelope
  transparently, so the entire existing app works over mobile data with
  no per-screen changes — JWT auth with automatic refresh + replay-safe
  nonces.
- Pairing payload parser reads the desktop's `paios://pair` QR (LAN +
  relay + account) or a plain address.
- Verified end to end on the now-working Flutter toolchain:
  `flutter analyze` clean, `flutter test` 89 passing, and a **release
  APK** (`app-release.apk`) builds successfully.

### Non-technical-user guarantee
- After installation, using local AI and connecting the Android app
  require no Command Prompt, PowerShell, environment variables,
  configuration files, or manual networking — everything is in the GUI.
