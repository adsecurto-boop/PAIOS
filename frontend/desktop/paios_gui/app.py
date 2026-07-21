"""Application assembly: config -> client -> themed window -> event loop."""

import argparse
import logging
import logging.handlers
import os
import sys

from PySide6.QtWidgets import QApplication

from paios_gui.client import ApiClient
from paios_gui.config import GuiConfig
from paios_gui.main_window import MainWindow
from paios_gui.theme import apply_dark_theme


def build_config(argv: list[str]) -> GuiConfig:
    parser = argparse.ArgumentParser(
        prog="paios-gui", description="PAIOS desktop dashboard"
    )
    parser.add_argument(
        "--url",
        default=GuiConfig.base_url,
        help="REST API base URL (default %(default)s)",
    )
    parser.add_argument(
        "--refresh",
        type=int,
        default=GuiConfig.refresh_seconds,
        help="poll interval in seconds (default %(default)s)",
    )
    parser.add_argument(
        "--log-dir",
        default=None,
        help="write paios-gui.log here (M16 structured logging)",
    )
    arguments = parser.parse_args(argv)
    config = GuiConfig(base_url=arguments.url)
    config.refresh_seconds = config.clamp_refresh(arguments.refresh)
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
    config = build_config(sys.argv[1:] if argv is None else argv)
    app = QApplication.instance() or QApplication([])
    apply_dark_theme(app)
    client = ApiClient(config.base_url, timeout=config.request_timeout)
    window = MainWindow(client, config)
    window.show()
    window.refresh_now()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
