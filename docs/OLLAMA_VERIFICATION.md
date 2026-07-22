# Ollama Real-Integration Verification

A 15-minute checklist proving PAIOS local AI works end to end on a
machine with Ollama actually installed. Run it once per release on real
hardware (the automated suite covers the pipeline with fakes; this
covers the last mile a CI box cannot).

Everything below uses the product UI where possible; the `curl`
equivalents are given for a scripted pass.

## 0. Preconditions

- PAIOS installed from `PAIOSSetup.exe` and running.
- Ollama installed from <https://ollama.com/download> (its tray icon
  is running). No models needed yet.

## 1. Detection

**UI:** first-run wizard (or a fresh data dir) → *Choose your PAIOS
Intelligence Mode* shows your RAM/CPU/GPU and a recommended model, and
does NOT show the "Ollama is not installed" hint.

**Scripted:**

```bash
curl http://127.0.0.1:8765/assistant/setup
```

PASS = `"ollama": {"server_running": true, ...}` and a
`recommended_models` list with exactly one `"recommended": true`.

## 2. Model download

**UI:** click *Install recommended model*. The status explains the
download runs in the background.

**Scripted:**

```bash
curl -X POST http://127.0.0.1:8765/assistant/ollama/pull -d "{\"model\": \"qwen2.5:7b\"}"
```

Poll until the model appears (size ≈ 4.7 GB):

```bash
curl http://127.0.0.1:8765/assistant/ollama
```

PASS = `models` contains `qwen2.5:7b`. While it downloads, every other
PAIOS request must keep answering instantly (the download is a
detached process — verify by opening the Planning page meanwhile).

## 3. Activation

**UI:** wizard → *Use local AI* (or Settings later).

**Scripted:**

```bash
curl -X PUT http://127.0.0.1:8765/assistant/config -d "{\"provider\": \"ollama\", \"model\": \"qwen2.5:7b\"}"
```

PASS = reply has `"available": true` — with no restart. Then:

```bash
curl http://127.0.0.1:8765/assistant/status
```

PASS = `{"provider": "ollama", "available": true, ...}`.

## 4. First real answer

```bash
curl -X POST http://127.0.0.1:8765/assistant/test
```

PASS = `"source": "llm"`, `"ok": true`, `"adapter": "ollama:qwen2.5:7b"`
and a short model-written sentence. (First call loads the model into
RAM — allow up to a minute; later calls are much faster.)

## 5. Real workflows

```bash
curl -X POST http://127.0.0.1:8765/assistant/morning-plan -d "{\"sleep_hours\": 6, \"energy\": \"medium\"}"
```

PASS = `"source": "llm"` with model-written `answer`/`bullets` AND the
deterministic `timeline`/`priorities`/`risks` fields still present.
Repeat for `/assistant/evening-review` and `/assistant/weekly-review`.

## 6. Offline proof (scenario 3)

Disconnect Wi-Fi/Ethernet entirely. Repeat steps 4–5.

PASS = identical behavior — local AI needs no internet.

## 7. From the phone (scenario 4 + AI)

With a paired phone (Mobile page → Generate pairing code):

- App → AI Assistant → ask "What's on my plan today?"

PASS = an answer WITHOUT the "Desktop AI is off" hint, i.e. the reply
came from Ollama through the desktop. Scripted equivalent:

```bash
curl -X POST http://<desktop-ip>:8765/mobile/assistant/query -H "Authorization: Bearer <token>" -d "{\"text\": \"What is on my plan today?\"}"
```

PASS = `"source": "llm"`, `"adapter": "ollama:qwen2.5:7b"`.

## 8. Fallback proof (scenario 5)

Quit Ollama from its tray icon. Ask the morning plan again.

PASS = `"source": "heuristic"` — a valid deterministic answer, no
error, no crash. Restart Ollama; the next request is `"llm"` again
(composition retries per request only on recompose — if it stays
heuristic, hit `PUT /assistant/config` again or restart PAIOS).

## Record the result

Add a line to the release notes:

```
Ollama verification: PASS — <machine>, <RAM> GB, <model>, <date>
```

Any FAIL step: file it against the matching module —
detection/`assistant/setup` → `paios/api/ollama_support.py`,
completion errors → `paios/assistant/adapters/ollama.py`,
fallback behavior → `paios/api/routes.py` + `assistant_support.py`.
