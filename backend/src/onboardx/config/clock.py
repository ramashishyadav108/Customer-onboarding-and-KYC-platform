"""Clock implementations (the Clock port lives in the domain). Tests inject a fixed clock."""

from datetime import UTC, datetime


class SystemClock:
    """Wall-clock UTC time."""

    def now(self) -> datetime:
        return datetime.now(UTC)
