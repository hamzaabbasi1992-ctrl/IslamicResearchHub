"""Entry point for the Islamic Research Hub desktop app.

Requires the optional "gui" dependency group (`pip install -e .[gui]`).
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow
from islamic_research_hub.shared.logging_config import configure_logging

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
DEFAULT_MAKNOON_PDF_FOLDER = Path(
    r"F:\Maknoon Mufahris Almakhtotaat (Search Able Urdu Pdf books Library)\PDF Data"
)


def main() -> int:
    """Launch the desktop app and run its event loop."""
    configure_logging(DEFAULT_LOG_DIRECTORY)
    app = QApplication(sys.argv)
    app.setApplicationName("Islamic Research Hub")
    window = MainWindow(
        DEFAULT_DATABASE_PATH, DEFAULT_MAKNOON_PDF_FOLDER, log_directory=DEFAULT_LOG_DIRECTORY
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
