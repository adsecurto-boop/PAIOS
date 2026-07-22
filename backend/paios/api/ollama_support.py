"""Ollama server management for the setup/settings surface (transport
concern; the assistant package never manages servers).

Everything is best-effort and injectable:

    fetcher(url, timeout) -> decoded JSON        (server queries)
    spawner(command) -> None                     (detached `ollama pull`)

Model downloads run as a DETACHED `ollama pull` process — the REST
server is deliberately single-threaded, so a multi-minute download must
never run inside a request. Clients poll GET /assistant/ollama until
the model appears in the installed list.
"""

import json
import os
import shutil
import subprocess
import urllib.request

import paios.system.hardware as hardware

_QUERY_TIMEOUT_SECONDS = 4


def default_fetcher(url: str, timeout: float):
    with urllib.request.urlopen(url, timeout=timeout) as reply:
        return json.loads(reply.read().decode("utf-8"))


def default_spawner(command: list[str]) -> None:
    creation_flags = 0
    if os.name == "nt":
        creation_flags = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW
        )
    subprocess.Popen(
        command,
        creationflags=creation_flags,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        close_fds=True,
    )


def cli_available(which=shutil.which) -> bool:
    return which("ollama") is not None


def status(base_url: str | None = None, fetcher=default_fetcher) -> dict:
    """One shape the setup wizard and settings page render directly."""
    from paios.assistant.adapters.ollama import resolve_base_url

    url = resolve_base_url(base_url)
    installed_models: list[dict] = []
    running = False
    try:
        payload = fetcher(f"{url}/api/tags", _QUERY_TIMEOUT_SECONDS)
        running = True
        for model in payload.get("models") or []:
            name = model.get("name")
            if name:
                installed_models.append(
                    {
                        "name": name,
                        "size_gb": round(
                            (model.get("size") or 0) / (1024**3), 1
                        ),
                    }
                )
    except Exception:
        running = False
    return {
        "cli_installed": cli_available(),
        "server_running": running,
        "base_url": url,
        "models": installed_models,
        "install_hint": (
            None
            if running
            else "Install Ollama from https://ollama.com/download and"
            " start it; PAIOS will detect it automatically."
        ),
    }


def start_pull(model: str, spawner=default_spawner) -> dict:
    """Launch a detached `ollama pull <model>`; the download continues
    independently of this server. Poll status() for completion."""
    if not cli_available():
        return {
            "started": False,
            "reason": "The ollama command line is not installed —"
            " install Ollama from https://ollama.com/download first.",
        }
    spawner(["ollama", "pull", model])
    return {
        "started": True,
        "model": model,
        "note": "Downloading in the background; the model appears in"
        " the installed list when ready.",
    }


def remove_model(model: str, runner=None) -> dict:
    """`ollama rm <model>` — synchronous (removal is fast)."""
    if not cli_available():
        return {"removed": False, "reason": "ollama CLI not installed"}
    run = runner if runner is not None else subprocess.run
    try:
        completed = run(
            ["ollama", "rm", model],
            capture_output=True, text=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return {"removed": False, "reason": str(error)}
    if completed.returncode != 0:
        return {
            "removed": False,
            "reason": (completed.stderr or completed.stdout or "").strip(),
        }
    return {"removed": True, "model": model}


def setup_report(base_url: str | None = None, fetcher=default_fetcher) -> dict:
    """Hardware + recommendations + server state: everything the
    "Choose your PAIOS Intelligence Mode" screen needs in one call."""
    profile = hardware.detect()
    recommendations = hardware.recommend_models(
        profile.ram_gb, profile.vram_gb
    )
    return {
        "hardware": profile.as_dict(),
        "recommended_models": [
            choice.as_dict() for choice in recommendations
        ],
        "ollama": status(base_url, fetcher),
    }
