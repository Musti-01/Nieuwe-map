"""Shared clock-in eligibility; the service always applies this policy again."""
from datetime import datetime, time, timedelta, timezone


def clock_in_opens_at(start, tz):
    midnight = datetime.combine(start.astimezone(tz).date(), time.min, tzinfo=tz)
    return max(start.astimezone(timezone.utc) - timedelta(minutes=10), midnight.astimezone(timezone.utc))


def clock_in_allowed(start, end, current, tz):
    return (current.astimezone(tz).date() == start.astimezone(tz).date()
            and clock_in_opens_at(start, tz) <= current.astimezone(timezone.utc) < end.astimezone(timezone.utc))
