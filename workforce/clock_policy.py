"""Shared clock-in eligibility; the service always applies this policy again."""
from datetime import timedelta


def clock_in_allowed(start, end, current, tz):
    return (current.astimezone(tz).date() == start.astimezone(tz).date()
            and start - timedelta(minutes=10) <= current < end)
