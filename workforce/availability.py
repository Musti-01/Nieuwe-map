"""Availability rule validation and expansion in the configured local timezone."""
from datetime import datetime, timedelta


MAX_RECURRENCE_DAYS = 366


def validate_rule(start, end, weekly=False, recurrence_until=None, tz=None):
    if not all(isinstance(v, datetime) and v.tzinfo is not None and v.utcoffset() is not None for v in (start, end)):
        raise ValueError("Geef begin- en eindtijd met tijdzone op.")
    local_start = start.astimezone(tz) if tz else start
    local_end = end.astimezone(tz) if tz else end
    if local_start.date() != local_end.date() or local_end <= local_start:
        raise ValueError("Beschikbaarheid moet op één dag liggen en het einduur moet na het beginuur liggen.")
    if weekly:
        if recurrence_until is None:
            raise ValueError("Kies een einddatum voor de wekelijkse beschikbaarheid.")
        if recurrence_until < local_start.date():
            raise ValueError("De herhaling kan niet vóór de eerste beschikbare dag eindigen.")
        if (recurrence_until - local_start.date()).days > MAX_RECURRENCE_DAYS:
            raise ValueError("Wekelijkse beschikbaarheid kan maximaal één jaar vooruit lopen.")
    elif recurrence_until is not None:
        raise ValueError("Een einddatum voor herhaling hoort alleen bij wekelijkse beschikbaarheid.")
    return local_start, local_end


def occurrences(rule, begin, end, tz):
    """Expand one rule into concrete aware datetime intervals intersecting [begin, end)."""
    first_start = rule.starts_at.astimezone(tz)
    first_end = rule.ends_at.astimezone(tz)
    if not rule.weekly:
        if first_start < end and first_end > begin:
            return [(rule.id, first_start, first_end)]
        return []

    until = rule.recurrence_until
    day = first_start.date()
    result = []
    while day <= until:
        start_local = datetime.combine(day, first_start.timetz().replace(tzinfo=None), tzinfo=tz)
        end_local = datetime.combine(day, first_end.timetz().replace(tzinfo=None), tzinfo=tz)
        if start_local < end and end_local > begin:
            result.append((rule.id, start_local, end_local))
        if start_local >= end and day > begin.astimezone(tz).date():
            break
        day += timedelta(days=7)
    return result
