"""config.yaml: deployment configuration, stdlib only.

The backend has zero runtime dependencies (a property every milestone
preserved), so PyYAML is not an option. PAIOS generates its own config
file, so it only needs to read what it writes: a documented YAML SUBSET
- top-level scalars, one level of nested mappings, comments, blank
lines, and scalar values (int, float, bool, null, quoted or bare
strings). Anything beyond that subset raises a clear error rather than
mis-parsing.

Relative paths in the file resolve against the config file's own
directory (the generated distribution config therefore uses ../data,
../logs, ../backups). Without a config file, legacy development
defaults apply (.data next to the working directory).
"""

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

CONFIG_ENV_VAR = "PAIOS_CONFIG"
DEFAULT_SEARCH = ("config/config.yaml", "config.yaml")


@dataclass(frozen=True)
class SystemConfig:
    data_dir: str = ".data"
    log_dir: str = ".logs"
    backup_dir: str = ".backups"
    server_host: str = "127.0.0.1"
    server_port: int = 8765
    gui_refresh_seconds: int = 5
    #: TUI dashboard interval; matches the M8 dashboard default (1s).
    dashboard_refresh_seconds: int = 1
    daemon_tick_seconds: float = 60.0
    quiet_hours: str | None = None
    notification_cooldown_seconds: int = 300
    backup_enabled: bool = True
    backup_interval_hours: float = 24.0
    backup_keep: int = 14
    #: Where this configuration came from (None = built-in defaults).
    source: str | None = field(default=None, compare=False)


# --- YAML subset ----------------------------------------------------------


def parse_yaml_subset(text: str) -> dict:
    """Parse the documented subset into {str: scalar | {str: scalar}}."""
    root: dict = {}
    current_section: dict | None = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        indented = line.startswith((" ", "\t"))
        key_part, separator, value_part = line.strip().partition(":")
        if not separator or not key_part.strip():
            raise ValueError(
                f"config line {line_number}: expected 'key: value', got"
                f" {raw_line.strip()!r}"
            )
        key = key_part.strip()
        value = value_part.strip()
        if indented:
            if current_section is None:
                raise ValueError(
                    f"config line {line_number}: indented value outside a"
                    " section"
                )
            current_section[key] = _scalar(value, line_number)
        elif value == "":
            current_section = {}
            root[key] = current_section
        else:
            current_section = None
            root[key] = _scalar(value, line_number)
    return root


def _scalar(token: str, line_number: int):
    if token in ("null", "~", ""):
        return None
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    if (token.startswith('"') and token.endswith('"') and len(token) >= 2) or (
        token.startswith("'") and token.endswith("'") and len(token) >= 2
    ):
        return token[1:-1]
    try:
        return int(token)
    except ValueError:
        pass
    try:
        return float(token)
    except ValueError:
        pass
    if token.startswith(("[", "{")):
        raise ValueError(
            f"config line {line_number}: collections are outside the"
            " supported YAML subset"
        )
    return token


# --- loading --------------------------------------------------------------


def load_system_config(explicit_path: str | None = None) -> SystemConfig:
    """Explicit path > $PAIOS_CONFIG > ./config/config.yaml > ./config.yaml
    > built-in defaults. A named-but-missing file is an error; the
    search locations are optional."""
    candidates: list[tuple[str, bool]] = []
    if explicit_path:
        candidates.append((explicit_path, True))
    elif os.environ.get(CONFIG_ENV_VAR):
        candidates.append((os.environ[CONFIG_ENV_VAR], True))
    else:
        candidates.extend((path, False) for path in DEFAULT_SEARCH)

    for path_text, required in candidates:
        path = Path(path_text)
        if path.is_file():
            return _from_file(path)
        if required:
            raise FileNotFoundError(f"Config file not found: {path}")
    return SystemConfig()


def _from_file(path: Path) -> SystemConfig:
    parsed = parse_yaml_subset(path.read_text(encoding="utf-8"))
    base = path.resolve().parent

    def _resolve(value: str) -> str:
        candidate = Path(value)
        return str(candidate if candidate.is_absolute() else (base / candidate))

    def section(name: str) -> dict:
        value = parsed.get(name)
        return value if isinstance(value, dict) else {}

    server = section("server")
    gui = section("gui")
    dashboard = section("dashboard")
    daemon = section("daemon")
    notifications = section("notifications")
    backup = section("backup")

    config = SystemConfig(
        data_dir=_resolve(str(parsed.get("data_dir", ".data"))),
        log_dir=_resolve(str(parsed.get("log_dir", ".logs"))),
        backup_dir=_resolve(str(parsed.get("backup_dir", ".backups"))),
        server_host=str(server.get("host", "127.0.0.1")),
        server_port=int(server.get("port", 8765)),
        gui_refresh_seconds=int(gui.get("refresh_seconds", 5)),
        dashboard_refresh_seconds=int(dashboard.get("refresh_seconds", 1)),
        daemon_tick_seconds=float(daemon.get("tick_interval_seconds", 60.0)),
        quiet_hours=(
            str(notifications["quiet_hours"])
            if notifications.get("quiet_hours") is not None
            else None
        ),
        notification_cooldown_seconds=int(
            notifications.get("cooldown_seconds", 300)
        ),
        backup_enabled=bool(backup.get("enabled", True)),
        backup_interval_hours=float(backup.get("interval_hours", 24.0)),
        backup_keep=int(backup.get("keep", 14)),
    )
    return replace(config, source=str(path.resolve()))


DEFAULT_CONFIG_TEMPLATE = """\
# PAIOS configuration (Milestone 16).
# Relative paths resolve against this file's directory.

data_dir: {data_dir}
log_dir: {log_dir}
backup_dir: {backup_dir}

server:
  host: 127.0.0.1
  port: 8765

gui:
  refresh_seconds: 5

dashboard:
  refresh_seconds: 1          # 0 renders one frame; allowed: 0/1/5/10

daemon:
  tick_interval_seconds: 60

notifications:
  quiet_hours: null          # e.g. 22:00-07:00 (critical bypasses)
  cooldown_seconds: 300

backup:
  enabled: true
  interval_hours: 24
  keep: 14
"""


def generate_default_config(
    path: str | Path,
    data_dir: str = "../data",
    log_dir: str = "../logs",
    backup_dir: str = "../backups",
) -> Path:
    """Write the commented default config (first-run initialization).
    Never overwrites an existing file."""
    target = Path(path)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        DEFAULT_CONFIG_TEMPLATE.format(
            data_dir=data_dir, log_dir=log_dir, backup_dir=backup_dir
        ),
        encoding="utf-8",
    )
    return target
