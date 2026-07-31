"""Logging configuration for command-line execution."""

import logging
from datetime import datetime
from pathlib import Path

DEFAULT_FRIENDLY_CAPACITY = 200


class FriendlyLogHandler(logging.Handler):
    """Keeps a bounded, in-memory list of short, human-readable INFO+ log
    lines, for the desktop app's friendly status view.

    Purely additive: attached alongside the existing console/file handlers
    in `configure_logging()`, never replacing them - every existing
    `LOGGER.info/exception(...)` call anywhere in the codebase keeps
    logging to the console/file exactly as before.
    """

    def __init__(self, capacity: int = DEFAULT_FRIENDLY_CAPACITY) -> None:
        super().__init__(level=logging.INFO)
        self._capacity = capacity
        self._messages: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Append a short "HH:MM:SS - message" line, dropping the oldest once full."""
        timestamp = datetime.fromtimestamp(record.created).strftime("%H:%M:%S")
        self._messages.append(f"{timestamp} - {record.getMessage()}")
        if len(self._messages) > self._capacity:
            self._messages.pop(0)

    def messages(self) -> list[str]:
        """Return the buffered friendly messages, newest first."""
        return list(reversed(self._messages))


_friendly_handler: FriendlyLogHandler | None = None


def configure_logging(log_directory: Path = Path("logs")) -> None:
    """Configure console, file, and friendly-status logging once for the application."""
    global _friendly_handler
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    log_directory.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(
        log_directory / "islamic_research_hub.log",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    _friendly_handler = FriendlyLogHandler()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(_friendly_handler)


def get_friendly_log_handler() -> FriendlyLogHandler | None:
    """Return the shared `FriendlyLogHandler`, if `configure_logging()` has run yet."""
    return _friendly_handler
