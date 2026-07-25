"""Entry point for the Islamic Research Hub desktop app.

Requires the optional "gui" dependency group (`pip install -e .[gui]`).
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from islamic_research_hub.interfaces.desktop_app.main_window import MainWindow
from islamic_research_hub.shared.logging_config import configure_logging

DEFAULT_DATABASE_PATH = Path("data/books.db")
DEFAULT_MAKNOON_PDF_FOLDER = Path(
    r"F:\Maknoon Mufahris Almakhtotaat (Search Able Urdu Pdf books Library)\PDF Data"
)


def main() -> int:
    """Launch the desktop app and run its event loop."""
    configure_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("Islamic Research Hub")
    window = MainWindow(DEFAULT_DATABASE_PATH, DEFAULT_MAKNOON_PDF_FOLDER)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
