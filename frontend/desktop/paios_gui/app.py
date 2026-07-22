"""Application assembly: config -> client -> themed window -> event loop.

M20 startup order: defaults < gui-settings.json (the first-run wizard's
output) < CLI flags. The wizard itself shows only when the settings
file carries no ``first_run_complete`` marker — and never when
--no-wizard is passed or Qt renders offscreen (tests).
"""

import argparse
import logging
import logging.handlers
import os
import sys

from PySide6.QtWidgets import QApplication

from paios_gui import settings_store
from paios_gui.client import ApiClient
from paios_gui.config import GuiConfig
from paios_gui.first_run_wizard import FirstRunWizard, should_show_wizard
from paios_gui.main_window import MainWindow
from paios_gui.theme import apply_dark_theme


def parse_arguments(argv: list[str], settings: dict) -> argparse.Namespace:
    """CLI flags with the settings file's values as their defaults —
    an omitted flag adopts the stored preference, a passed flag wins."""
    parser = argparse.ArgumentParser(
        prog="paios-gui", description="PAIOS desktop dashboard"
    )
    parser.add_argument(
        "--url",
        default=settings.get("base_url", GuiConfig.base_url),
        help="REST API base URL (default %(default)s)",
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=settings.get(
            "refresh_seconds", GuiConfig.refresh_seconds
        ),
        help="poll interval in seconds (default %(default)s)",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="write paios-gui.log here (M16 structured logging)",
    )
    parser.add_argument(
        "--no-wizard",
        action="store_true",
        help="never show the first-run wizard",
    )
    return parser.parse_args(argv)


def build_config(argv: list[str], settings: dict | None = None) -> GuiConfig:
    stored = settings if settings is not None else (
        settings_store.load_settings()
    )
    arguments = parse_arguments(argv, stored)
    config = GuiConfig(base_url=arguments.url)
    config.refresh_seconds = config.clamp_refresh(arguments.refresh)
    config.log_dir = arguments.log_dir
    if arguments.log_dir:
        _setup_logging(arguments.log_dir)
    return config


def _setup_logging(log_dir: str) -> None:
    """Same structured line format as the backend surfaces; plain
    stdlib logging — the GUI still imports nothing from the backend.
    The log sink is the one sanctioned file output (M16); domain data
    still never touches the GUI's disk (the M13 rule stands)."""
    os.makedirs(log_dir, exist_ok=True)
    handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "paios-gui.log"),
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger = logging.getLogger("paios.gui")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    logger.addHandler(handler)


def main(argv: list[str] | None = None) -> int:
    raw_argv = sys.argv[1:] if argv is None else argv
    settings = settings_store.load_settings()
    arguments = parse_arguments(raw_argv, settings)
    config = GuiConfig(base_url=arguments.url)
    config.refresh_seconds = config.clamp_refresh(arguments.refresh)
    config.log_dir = arguments.log_dir
    if arguments.log_dir:
        _setup_logging(arguments.log_dir)

    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)

    if should_show_wizard(settings, no_wizard=arguments.no_wizard):
        wizard = FirstRunWizard(
            base_url=config.base_url,
            refresh_seconds=config.refresh_seconds,
        )
        if wizard.exec():
            chosen = wizard.settings()
            settings_store.save_settings(chosen)
            config.base_url = chosen["base_url"]
            config.refresh_seconds = config.clamp_refresh(
                chosen["refresh_seconds"]
            )
        else:
            # Declined: remember that, so the wizard stays a one-time
            # greeting rather than a recurring gate.
            settings_store.save_settings({"first_run_complete": True})

    client = ApiClient(config.base_url, timeout=config.request_timeout)
    window = MainWindow(client, config)
    window.show()
    window.refresh_now()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
