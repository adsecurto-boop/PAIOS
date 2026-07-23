"""CLI entry point: one-shot commands, the interactive shell, and the
process-bound surfaces (serve, dashboard, gui, daemon, backup, health,
init).

Each process composes its own Application (composition-root privilege
via the Application facade only). Deployment concerns (M16) are wired
here: config.yaml defaults, structured logging, bus log observation,
backups, health checks — always through public surfaces.

Option precedence: explicit flags > config.yaml > built-in defaults.
"""

import shlex
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import TextIO

from paios.application.application import Application
from paios.application.config import ApplicationConfig
from paios.cli.commands import CommandProcessor, build_dashboard_config
from paios.cli.exceptions import CliError
from paios.cli.formatter import format_help
from paios.cli.interactive import Shell
from paios.cli.parser import COMMAND_SPECS, parse_line
from paios.dashboard import Dashboard
from paios.notifications import (
    ConsoleProvider,
    NotificationConfig,
    NotificationManager,
    NullProvider,
    QuietHours,
)
from paios.system import (
    BackupManager,
    BusLogObserver,
    LogProvider,
    generate_default_config,
    load_system_config,
    run_health_checks,
    setup_logging,
)
from paios.system.backup import BackupError, BackupPolicy
from paios.system.config import SystemConfig
from paios.system import daemon_runner


def _split_options(
    argv: list[str],
) -> tuple[ApplicationConfig, NotificationConfig, SystemConfig, list[str]]:
    data_dir: str | None = None
    quiet_hours: QuietHours | None = None
    config_path: str | None = None
    rest: list[str] = []
    index = 0
    while index < len(argv):
        if argv[index] == "--data-dir" and index + 1 < len(argv):
            data_dir = argv[index + 1]
            index += 2
        elif argv[index] == "--config" and index + 1 < len(argv):
            config_path = argv[index + 1]
            index += 2
        elif argv[index] == "--quiet-hours" and index + 1 < len(argv):
            try:
                quiet_hours = QuietHours.parse(argv[index + 1])
            except ValueError as error:
                raise CliError(str(error)) from error
            index += 2
        else:
            rest.append(argv[index])
            index += 1

    try:
        system = load_system_config(config_path)
    except (FileNotFoundError, ValueError) as error:
        raise CliError(str(error)) from error

    if quiet_hours is None and system.quiet_hours is not None:
        try:
            quiet_hours = QuietHours.parse(system.quiet_hours)
        except ValueError as error:
            raise CliError(f"config quiet_hours: {error}") from error

    effective_data_dir = data_dir if data_dir is not None else system.data_dir
    # Without a config file, logs live inside the data directory —
    # development and test runs stay self-contained.
    effective_log_dir = (
        system.log_dir
        if system.source is not None
        else str(Path(effective_data_dir) / "logs")
    )
    system = replace(
        system, data_dir=effective_data_dir, log_dir=effective_log_dir
    )
    # M20: every product surface schedules with the MetadataPlanner
    # (durations/deadlines/dependencies from the planning sidecar) —
    # injected through the Scheduler's existing R3 constructor seam.
    from paios.planning.metadata_planner import MetadataPlanner
    from paios.planning.stores import EventMetadataStore

    planner = MetadataPlanner(
        EventMetadataStore(Path(effective_data_dir) / "planning")
    )
    return (
        ApplicationConfig(data_dir=effective_data_dir, planner=planner),
        NotificationConfig(
            quiet_hours=quiet_hours,
            cooldown_seconds=system.notification_cooldown_seconds,
        ),
        system,
        rest,
    )


def _backup_manager(system: SystemConfig) -> BackupManager:
    return BackupManager(
        system.data_dir,
        system.backup_dir,
        BackupPolicy(
            enabled=system.backup_enabled,
            interval_hours=system.backup_interval_hours,
            keep=system.backup_keep,
        ),
    )


def _launch_detached(command: list[str]) -> int:
    """Start a sibling process (the GUI) detached; returns its pid."""
    flags = 0
    if sys.platform == "win32":
        flags = (
            subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
    process = subprocess.Popen(command, creationflags=flags)
    return process.pid


def main(
    argv: list[str] | None = None,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    out = output_stream if output_stream is not None else sys.stdout
    try:
        config, notification_config, system, arguments = _split_options(argv)
    except CliError as error:
        out.write(f"Error: {error}\n")
        return 1

    if not arguments:
        out.write(format_help(COMMAND_SPECS) + "\n")
        return 0

    # --- process-bound M16 surfaces (no Application instance needed) -----

    if arguments[0] == "init":
        return _run_init(system, out)

    if arguments[0] == "health":
        setup_logging(system.log_dir, "cli")
        checks = run_health_checks(system)
        for check in checks:
            marker = "OK  " if check.ok else "FAIL"
            out.write(f"{marker} {check.component:<14} {check.detail}\n")
        healthy = all(check.ok for check in checks)
        out.write("All checks passed.\n" if healthy else "Problems found.\n")
        return 0 if healthy else 1

    if arguments[0] == "gui":
        url = f"http://{system.server_host}:{system.server_port}"
        command = [
            sys.executable,
            "-m",
            "paios_gui",
            "--url",
            url,
            "--refresh",
            str(system.gui_refresh_seconds),
            "--log-dir",
            system.log_dir,
        ]
        try:
            pid = _launch_detached(command)
        except OSError as error:
            out.write(f"Error: could not launch the GUI: {error}\n")
            return 1
        out.write(f"GUI launched (pid {pid}), talking to {url}.\n")
        return 0

    if arguments[0] == "daemon":
        return _run_daemon(system, notification_config, arguments[1:], out)

    if arguments[0] == "backup":
        setup_logging(system.log_dir, "cli")
        return _run_backup(system, arguments[1:], out)

    # --- application-hosting surfaces ------------------------------------

    application = Application(config)
    log_observer = BusLogObserver()
    # The shell narrates to its stream; one-shot runs stay quiet (their
    # output contract predates M14). Both write the structured log.
    providers = (
        (ConsoleProvider(out), LogProvider())
        if arguments[0] == "shell"
        else (NullProvider(), LogProvider())
    )
    notifications = NotificationManager(notification_config, providers)
    processor = CommandProcessor(
        application, notifications, bus_observer=log_observer
    )

    if arguments[0] == "shell":
        setup_logging(system.log_dir, "cli")
        source = input_stream if input_stream is not None else sys.stdin
        Shell(processor, source, out).run()
        if application.started:
            application.stop()
        return 0

    if arguments[0] == "serve":
        from paios.api import ApiConfig, ApiServer
        from paios.system import network

        setup_logging(system.log_dir, "api")
        try:
            port = system.server_port
            if len(arguments) > 1:
                if not arguments[1].isdigit():
                    raise CliError(
                        f"Port must be a number, got {arguments[1]!r}"
                    )
                port = int(arguments[1])
            application.start()
            log_observer.attach(application.components.kernel.event_bus)
            notifications.attach(
                application.components.kernel.event_bus,
                started_at=application.components.clock.now(),
            )
            # M21: the persisted Local/LAN choice (Networking page) wins
            # over the configured host, so the toggle needs no terminal.
            bind_host = network.resolve_bind_host(
                str(config.data_dir), system.server_host
            )
            server = ApiServer(
                ApiConfig(
                    host=bind_host,
                    port=port,
                    data_dir=str(config.data_dir),
                ),
                application=application,
            )
            server.start()
            out.write(
                f"PAIOS API listening on http://{bind_host}:"
                f"{server.port}  (Ctrl+C to stop)\n"
            )
            out.flush()
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
            finally:
                server.shutdown()
                if application.started:
                    application.stop()
                out.write("PAIOS API stopped.\n")
                out.flush()
            return 0
        except CliError as error:
            out.write(f"Error: {error}\n")
            if application.started:
                application.stop()
            return 1

    if arguments[0] == "dashboard":
        setup_logging(system.log_dir, "dashboard")
        try:
            # Explicit CLI argument > config.yaml dashboard interval >
            # built-in default (M18: the M16 knob is now actually wired).
            dashboard_arguments = arguments[1:]
            if not dashboard_arguments and system.source is not None:
                dashboard_arguments = [str(system.dashboard_refresh_seconds)]
            dashboard_config = build_dashboard_config(dashboard_arguments)
            application.start()
            log_observer.attach(application.components.kernel.event_bus)
            Dashboard(
                application, dashboard_config, output_stream=out
            ).run()
            application.stop()
            return 0
        except CliError as error:
            out.write(f"Error: {error}\n")
            if application.started:
                application.stop()
            return 1

    setup_logging(system.log_dir, "cli")
    try:
        # Re-quote argv tokens so multi-word arguments the OS shell already
        # grouped survive the line-oriented parser unchanged.
        command = parse_line(" ".join(shlex.quote(a) for a in arguments))
        if command is None:
            out.write(format_help(COMMAND_SPECS) + "\n")
            return 0
        needs_app = command.name not in ("help", "start", "stop")
        if needs_app or command.name == "stop":
            application.start()
        out.write(processor.execute(command) + "\n")
        if application.started:
            application.stop()
        return 0
    except CliError as error:
        out.write(f"Error: {error}\n")
        return 1
    except Exception as error:
        out.write(f"Error: {error}\n")
        if application.started:
            application.stop()
        return 1


# --- M16 subcommand bodies -------------------------------------------------


def _run_init(system: SystemConfig, out: TextIO) -> int:
    """First-run initialization: config file + directory skeleton."""
    if system.source is None:
        target = generate_default_config(
            Path("config") / "config.yaml",
            data_dir="../data",
            log_dir="../logs",
            backup_dir="../backups",
        )
        out.write(f"Created default configuration: {target}\n")
        system = load_system_config(str(target))
    else:
        out.write(f"Using configuration: {system.source}\n")
    for label, directory in (
        ("data", system.data_dir),
        ("logs", system.log_dir),
        ("backups", system.backup_dir),
    ):
        Path(directory).mkdir(parents=True, exist_ok=True)
        out.write(f"Ready: {label} directory {directory}\n")
    out.write("PAIOS initialized. Try `paios health`, then `paios shell`.\n")
    return 0


def _run_daemon(
    system: SystemConfig,
    notification_config: NotificationConfig,
    arguments: list[str],
    out: TextIO,
) -> int:
    action = arguments[0] if arguments else "status"
    if action == "run":
        setup_logging(system.log_dir, "daemon")

        def build_observers(application: Application):
            bus = application.components.kernel.event_bus
            observer = BusLogObserver()
            observer.attach(bus)
            manager = NotificationManager(
                notification_config, (ConsoleProvider(out), LogProvider())
            )
            manager.attach(
                bus, started_at=application.components.clock.now()
            )

            def detach() -> None:
                manager.detach()
                observer.detach()

            return detach

        return daemon_runner.run_foreground(
            system, build_observers=build_observers, output=out
        )
    if action == "start":
        out.write(daemon_runner.start_background(system) + "\n")
        return 0
    if action == "stop":
        out.write(daemon_runner.stop_background(system) + "\n")
        return 0
    if action == "restart":
        out.write(daemon_runner.restart_background(system) + "\n")
        return 0
    if action == "status":
        out.write(f"Daemon: {daemon_runner.daemon_status(system)}\n")
        return 0
    out.write(
        "Error: Usage: paios daemon <run|start|stop|restart|status>\n"
    )
    return 1


def _run_backup(
    system: SystemConfig, arguments: list[str], out: TextIO
) -> int:
    manager = _backup_manager(system)
    action = arguments[0] if arguments else "list"
    try:
        if action == "now":
            archive = manager.create()
            out.write(f"Backup created: {archive}\n")
            return 0
        if action == "list":
            backups = manager.list_backups()
            if not backups:
                out.write("No backups yet. Create one with `paios backup now`.\n")
                return 0
            for archive in backups:
                out.write(f"{archive.name}\n")
            return 0
        if action in ("restore", "import") and len(arguments) == 2:
            if "running (pid" in daemon_runner.daemon_status(system):
                out.write(
                    "Error: stop the daemon before restoring"
                    " (`paios daemon stop`).\n"
                )
                return 1
            names = (
                manager.restore(arguments[1])
                if action == "restore"
                else manager.import_from(arguments[1])
            )
            out.write(
                f"Restored {len(names)} store file(s) into"
                f" {system.data_dir}.\n"
            )
            return 0
        if action == "export" and len(arguments) == 2:
            target = manager.export_to(arguments[1])
            out.write(f"Exported store to: {target}\n")
            return 0
    except BackupError as error:
        out.write(f"Error: {error}\n")
        return 1
    out.write(
        "Error: Usage: paios backup"
        " <now|list|restore <name>|export <path>|import <path>>\n"
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
