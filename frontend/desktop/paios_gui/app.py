"""Application assembly: config -> client -> themed window -> event loop."""

import argparse
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
    arguments = parser.parse_args(argv)
    config = GuiConfig(base_url=arguments.url)
    config.refresh_seconds = config.clamp_refresh(arguments.refresh)
    return config


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
