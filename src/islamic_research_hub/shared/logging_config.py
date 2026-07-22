"""Logging configuration for command-line execution."""

import logging
from pathlib import Path


def configure_logging(log_directory: Path = Path("logs")) -> None:
    """Configure console and file logging once for the application."""
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
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
