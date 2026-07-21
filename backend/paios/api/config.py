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
