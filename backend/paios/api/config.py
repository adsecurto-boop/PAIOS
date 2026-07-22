"""API configuration: the only knobs the transport needs."""

from dataclasses import dataclass

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


@dataclass(frozen=True)
class ApiConfig:
    #: Bind address; loopback by default (no authentication exists yet).
    host: str = DEFAULT_HOST
    #: TCP port; 0 lets the OS choose (ephemeral — used by tests).
    port: int = DEFAULT_PORT
    #: Storage location handed to the composed Application.
    data_dir: str = ".data"
    #: M20: where /backups archives live. None -> "<data_dir>/../backups"
    #: mirrors the installer layout; a plain ".backups" for dev runs.
    backup_dir: str | None = None
    #: M20: assistant provider — "none" (deterministic heuristics only),
    #: "null" (offline canned adapter), "anthropic" or "openai".
    #: Environment variables PAIOS_AI_PROVIDER / PAIOS_AI_MODEL override
    #: at composition time; SDK API keys come from the SDKs' own
    #: standard environment variables, never from this config.
    ai_provider: str = "none"
    ai_model: str | None = None
