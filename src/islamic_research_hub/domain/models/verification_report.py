"""Typed models for database integrity verification results."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VerificationIssue:
    """One integrity problem found in the master database."""

    severity: str
    category: str
    message: str


@dataclass(frozen=True, slots=True)
class VerificationReport:
    """The complete result of one database verification run."""

    issues: tuple[VerificationIssue, ...]

    @property
    def error_count(self) -> int:
        """Return how many issues are errors (as opposed to warnings)."""
        return sum(1 for issue in self.issues if issue.severity == "error")

    @property
    def warning_count(self) -> int:
        """Return how many issues are warnings (as opposed to errors)."""
        return sum(1 for issue in self.issues if issue.severity == "warning")

    @property
    def is_healthy(self) -> bool:
        """Return whether the database has no errors (warnings are still allowed)."""
        return self.error_count == 0
