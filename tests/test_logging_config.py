"""Tests for `FriendlyLogHandler`.

Tests it in isolation against a private logger (never the real root
logger `configure_logging()` touches) - attaching to the actual root
logger would leak log records from unrelated tests running in the same
process into the buffer, making these tests non-deterministic.
"""

import logging

from islamic_research_hub.shared.logging_config import FriendlyLogHandler


def _make_logger(name: str, handler: FriendlyLogHandler) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def test_starts_empty() -> None:
    """A fresh handler has no buffered messages."""
    handler = FriendlyLogHandler()

    assert handler.messages() == []


def test_records_a_short_human_readable_line() -> None:
    """An INFO record becomes a short "HH:MM:SS - message" line."""
    handler = FriendlyLogHandler()
    logger = _make_logger("test.friendly.one", handler)

    logger.info("Imported 5 books")

    assert len(handler.messages()) == 1
    assert handler.messages()[0].endswith(" - Imported 5 books")


def test_ignores_debug_records() -> None:
    """DEBUG records are filtered out - only INFO and above are friendly-logged."""
    handler = FriendlyLogHandler()
    logger = _make_logger("test.friendly.two", handler)

    logger.debug("verbose internal detail")

    assert handler.messages() == []


def test_messages_are_returned_newest_first() -> None:
    """The most recently logged message comes first."""
    handler = FriendlyLogHandler()
    logger = _make_logger("test.friendly.three", handler)

    logger.info("first event")
    logger.info("second event")

    assert [msg.split(" - ", 1)[1] for msg in handler.messages()] == [
        "second event",
        "first event",
    ]


def test_drops_the_oldest_message_once_over_capacity() -> None:
    """A bounded buffer never grows past its capacity."""
    handler = FriendlyLogHandler(capacity=3)
    logger = _make_logger("test.friendly.four", handler)

    for i in range(5):
        logger.info(f"event {i}")

    messages = [msg.split(" - ", 1)[1] for msg in handler.messages()]
    assert messages == ["event 4", "event 3", "event 2"]


def test_formats_message_arguments_like_standard_logging() -> None:
    """`%`-style args are interpolated, matching normal logging behavior."""
    handler = FriendlyLogHandler()
    logger = _make_logger("test.friendly.five", handler)

    logger.info("Imported %d, skipped %d", 5, 2)

    assert handler.messages()[0].endswith(" - Imported 5, skipped 2")
