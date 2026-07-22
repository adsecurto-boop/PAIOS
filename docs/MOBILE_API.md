# PAIOS Mobile API

The `/mobile` namespace: how the Android companion talks to the PAIOS
desktop. The phone is an interface, capture device and remote — the
desktop stores the memory, runs the AI, and manages the life system.

```
Android app (Flutter, frontend/mobile)
        |  Bearer token over the local network
Secure Mobile API (/mobile/*)
        |
PAIOS Desktop Core (Scheduler, Decision Engine)
        |
JSON store + optional AI (Ollama / cloud)
```

## Security model

- **Nothing is exposed by default**: the API binds to `127.0.0.1`.
  To accept the phone, start it LAN-reachable
  (`python -m paios.api --host 0.0.0.0`, or the config file's
  `server.host`) and allow TCP 8765 through the firewall for private
  networks.
- **Device pairing**: trust is created on the desktop's initiative
  with a 6-digit, 5-minute, single-use code. Pairing administration
  (`/mobile/pairing/*`) answers loopback callers only — a device on
  the network can never start a pairing.
- **Bearer tokens**: pairing issues a token shown exactly once; the
  desktop stores only its SHA-256. Every `/mobile` data call requires
  `Authorization: Bearer <token>` and returns 401 otherwise. Devices
  can be listed and revoked at any time.
- **HTTPS-ready**: the scheme is transport-agnostic; putting the API
  behind TLS (reverse proxy or a later built-in) changes nothing in
  the pairing/token model. For off-network access today, use a private
  tunnel (Tailscale/WireGuard).

## Pairing flow

```
Desktop                              Phone
-------                              -----
POST /mobile/pairing/start
 -> {"code": "123456",
     "expires_at": ...}
   (desktop shows the code)
                                     POST /mobile/pair
                                      {"code": "123456",
                                       "device_name": "Pixel 8"}
                                      -> 201 {"device_id": ...,
                                              "token": "..."}   (once!)
                                     stores token securely
                                     Authorization: Bearer <token>
                                     on every later call
```

`POST /mobile/auth {"token": ...}` validates a stored token (app
start / settings check): `200 {"valid": true}` or `401`.

## Endpoints

All authenticated with the bearer token unless noted.

| Route | Method | Purpose |
|-------|--------|---------|
| `/mobile/pairing/start` | POST | (desktop, loopback-only) begin pairing, returns the code |
| `/mobile/pairing/devices` | GET | (desktop, loopback-only) trusted devices |
| `/mobile/pairing/devices/{id}` | DELETE | (desktop, loopback-only) revoke a device |
| `/mobile/pair` | POST | complete pairing with the code → token (no auth) |
| `/mobile/auth` | POST | validate a token (no auth header needed) |
| `/mobile/timeline` | GET | today's plan entries with per-entry WHY + `server_time` |
| `/mobile/tasks` | GET | all events (same shape as desktop `/events`) |
| `/mobile/tasks` | POST | create a task `{"title", "priority"?}` — rides the normal intent → Scheduler pipeline |
| `/mobile/logs` | GET | daily log entries; `/mobile/logs/{YYYY-MM-DD}` filters by day |
| `/mobile/logs` | POST | capture `{"kind", "text", "at"?, "client_id"?}`; kinds: `journal, mood, energy, sleep, note, study` |
| `/mobile/study` | GET | knowledge items + study logs |
| `/mobile/assistant/query` | POST | `{"text"}` → `{"source": "llm"\|"heuristic", "answer", "bullets", "confidence"}` |

## Offline-first sync contract

The phone works without the laptop: it stores timeline/tasks/notes/logs
locally and queues captures. The server side makes the queue safe:

- **Idempotency**: `POST /mobile/logs` with a `client_id` the device
  generated is a no-op if that `client_id` was already stored — the
  original record is returned. Flushing an offline queue twice (or
  after a half-failed flush) can never create duplicates.
- **Timestamps**: the capture may carry its true creation time in
  `at` (ISO-8601); without it the server's clock stamps arrival.
  `server_time` in timeline/tasks responses lets the client detect
  clock skew.
- **Conflicts**: logs are append-only facts (no edits), so
  last-writer-wins situations don't arise; tasks created from the
  phone go through the same Recommendation → Scheduler pipeline as
  desktop ones — the desktop remains the single authority.

Recommended client behavior (implemented in the Flutter app): capture
locally first, mark entries "pending sync", flush the queue whenever
connectivity returns, and treat every 401 as "re-pair needed".

## AI from the phone

`POST /mobile/assistant/query` uses whatever intelligence mode the
desktop is in. The phone never runs models: with local Ollama the
answer never leaves the house; with no provider the deterministic
engine answers (`"source": "heuristic"`) and the app shows a hint
rather than an error.

## Example session

```bash
# Desktop (loopback):
curl -X POST http://127.0.0.1:8765/mobile/pairing/start
# -> {"code": "482913", ...}   show it to the user

# Phone (LAN):
curl -X POST http://192.168.1.20:8765/mobile/pair \
     -d '{"code": "482913", "device_name": "Pixel 8"}'
# -> {"device_id": "device_a1b2c3", "token": "Xy...48chars"}

curl http://192.168.1.20:8765/mobile/timeline \
     -H "Authorization: Bearer Xy...48chars"
```
