"""Entry point for the Islamic Research Hub desktop app.

Requires the optional "gui" dependency group (`pip install -e .[gui]`).
"""

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QSettings
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from islamic_research_hub.interfaces.desktop_app.i18n import (
    SETTINGS_APPLICATION,
    SETTINGS_ORGANIZATION,
)
from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow
from islamic_research_hub.interfaces.desktop_app.theme_controller import ThemeController
from islamic_research_hub.shared.logging_config import configure_logging
from islamic_research_hub.shared.maktaba_link import parse_maktaba_link

# A packaged exe's working directory depends on how it was launched (double
# click, shortcut, command line) and can't be relied on - resolve paths
# relative to the exe itself instead. In dev mode (`python -m ...`), keep
# the existing CWD-relative behavior, matching the CLI tools.
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).resolve().parent
else:
    _BASE_DIR = Path.cwd()

DEFAULT_DATABASE_PATH = _BASE_DIR / "data" / "books.db"
DEFAULT_LOG_DIRECTORY = _BASE_DIR / "logs"
DEFAULT_ICON_PATH = _BASE_DIR / "assets" / "app_icon.ico"
DEFAULT_MAKNOON_PDF_FOLDER = Path(
    r"F:\Maknoon Mufahris Almakhtotaat (Search Able Urdu Pdf books Library)\PDF Data"
)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line argument parser."""
    parser = argparse.ArgumentParser(description="Launch the Islamic Research Hub desktop app.")
    parser.add_argument(
        "link",
        nargs="?",
        default=None,
        help=(
            "Optional maktaba://open?book=<id>&page=<n> link "
            "(see shared/maktaba_link.py) to jump straight to on launch."
        ),
    )
    return parser


def main() -> int:
    """Launch the desktop app and run its event loop.

    A `maktaba://` link passed on the command line (see `build_parser()`)
    opens straight to that book/page - the launch path a registered
    `maktaba://` Windows protocol handler uses, so a citation link in an
    exported document can jump straight to the real source page.
    """
    configure_logging(DEFAULT_LOG_DIRECTORY)
    args, _ = build_parser().parse_known_args()
    app = QApplication(sys.argv)
    app.setApplicationName("Islamic Research Hub")
    if DEFAULT_ICON_PATH.is_file():
        app.setWindowIcon(QIcon(str(DEFAULT_ICON_PATH)))
    settings = QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)
    app.setStyleSheet(ThemeController(settings).stylesheet())
    window = MainWindow(
        DEFAULT_DATABASE_PATH,
        DEFAULT_MAKNOON_PDF_FOLDER,
        settings=settings,
        log_directory=DEFAULT_LOG_DIRECTORY,
    )
    window.show()
    if args.link:
        target = parse_maktaba_link(args.link)
        if target is not None:
            window.open_book_at_page(*target)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
