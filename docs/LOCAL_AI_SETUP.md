# PAIOS Local AI Setup (Ollama)

Local AI is the recommended PAIOS intelligence mode: **free, private,
runs on your computer, works offline after setup.** Nothing you write
ever leaves your machine.

Ollama and its models are optional and are **never bundled** with the
PAIOS installer — PAIOSSetup.exe stays small, and PAIOS works fully
without them (deterministic Basic Mode).

## 1. Install Ollama

1. Download from <https://ollama.com/download> (Windows installer).
2. Run it. Ollama starts automatically and listens on
   `http://127.0.0.1:11434`.
3. Verify:

```bash
ollama --version
```

PAIOS detects a running Ollama automatically — no configuration needed.

## 2. Pick and install a model

Easiest: PAIOS first-run wizard or **Settings → AI** shows your
detected hardware and a recommended model with an *Install recommended
model* button (the download runs in the background; a few GB).

By hand, any of the supported models:

```bash
ollama pull qwen2.5:7b
```

Supported (what PAIOS recommends from, by machine size):

| Your RAM | Good choices | PAIOS recommends |
|----------|--------------|------------------|
| 8 GB | `qwen2.5:3b`, `llama3.2:3b` | Qwen2.5 3B |
| 16 GB | `qwen2.5:7b`, `llama3.1:8b`, `mistral:7b` | Qwen2.5 7B |
| 32 GB+ | `qwen2.5:14b` and larger | Qwen2.5 14B |

A discrete NVIDIA GPU speeds everything up and lets you run one size
larger comfortably. The recommendation is only a default — you can
choose any installed model in Settings.

## 3. Turn it on in PAIOS

First-run wizard → **Local AI (Recommended)** → *Use local AI*.

Or later: **Settings → AI → Provider: Local Ollama**, pick the model,
then *Test AI*. Or via the API/environment:

```bash
setx PAIOS_AI_PROVIDER ollama
setx PAIOS_AI_MODEL qwen2.5:7b
```

`GET http://127.0.0.1:8765/assistant/status` should then report
`"provider": "ollama", "available": true`.

## 4. What PAIOS uses it for

- **Morning planning** — commentary, priorities and risk flags over
  the day's schedule (the Scheduler still owns the schedule).
- **Evening review** — factual summary of the day, improvement
  observations, tomorrow preview.
- **Weekly review** — trends across the week.
- **Planning proposals** — classifying your captured thoughts into
  goals/projects/events for your approval.
- **Questions** — answers grounded in your own data, from the phone or
  desktop.

Every one of these also works without AI (deterministic versions) —
AI adds language, not capability.

## 5. Managing models

| Action | Settings UI | Command line |
|--------|-------------|--------------|
| List installed | Settings → AI | `ollama list` |
| Download | *Install model* | `ollama pull <model>` |
| Remove | *Remove model* | `ollama rm <model>` |
| Test | *Test AI* | `POST /assistant/test` |

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| status says "Ollama is not reachable" | Start Ollama (it runs as a tray app); check `http://127.0.0.1:11434` in a browser |
| "Ollama has no model ..." | The model isn't pulled yet — `ollama pull <model>` or the Install button |
| Answers are slow | Choose a smaller model (3B), close memory-heavy apps, or use a GPU |
| Ollama on another machine/port | set `PAIOS_OLLAMA_URL=http://host:11434` |
| Nothing works | PAIOS still plans deterministically — AI trouble never breaks PAIOS |
