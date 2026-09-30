"""UTC timestamp helpers: storage and API format is ISO-8601 with a trailing Z."""

from datetime import UTC, datetime


def to_iso_z(moment: datetime) -> str:
    """Format an aware datetime as UTC ``YYYY-MM-DDTHH:MM:SSZ`` (whole seconds)."""
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value: str) -> datetime:
    """Parse ``...Z`` or ``...+00:00`` timestamps to an aware UTC datetime."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
