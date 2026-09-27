"""Clock-time helpers. Raw data uses "HH:MM"; code uses minutes since midnight."""


def to_minutes(hhmm: str) -> int:
    """Parse "HH:MM" into minutes since midnight."""
    hours, minutes = hhmm.strip().split(":")
    return int(hours) * 60 + int(minutes)


def to_hhmm(minute: float) -> str:
    """Format minutes since midnight as "HH:MM" (rounded to the minute)."""
    m = round(minute)
    return f"{m // 60:02d}:{m % 60:02d}"
