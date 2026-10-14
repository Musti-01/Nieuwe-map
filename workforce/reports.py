from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

def period_bounds(day, period, zone="Europe/Brussels"):
    if period == "Week":
        day -= timedelta(days=day.weekday())
        end = day + timedelta(days=7)
    elif period == "Maand":
        day = day.replace(day=1)
        end = (day.replace(day=28) + timedelta(days=4)).replace(day=1)
    else:
        end = day + timedelta(days=1)
    tz = ZoneInfo(zone)
    return tuple(datetime.combine(d, time.min, tzinfo=tz).astimezone(timezone.utc) for d in (day, end))

def hours(entries, begin, end, as_of):
    totals = {}
    for e in entries:
        start, stop = max(e['start'], begin), min(e['end'] or as_of, end)
        if stop > start:
            key = (e['user_id'], e['name'])
            totals[key] = totals.get(key, 0) + (stop - start).total_seconds() / 3600
    return [{"Medewerker": name, "Uren": round(value, 2)} for (_, name), value in totals.items()]
