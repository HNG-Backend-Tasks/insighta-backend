from datetime import datetime, UTC


def utcnow() -> datetime:
    """Returns current UTC time as a naive datetime (timezone-stripped).
    Use everywhere instead of datetime.now() to avoid offset-naive vs
    offset-aware comparison errors with SQLite."""
    return datetime.now(UTC).replace(tzinfo=None)
