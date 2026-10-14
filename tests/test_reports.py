from datetime import date, datetime, timezone, timedelta
from workforce.reports import period_bounds, hours


def test_period_clips_midnight_crossing():
    begin, end = period_bounds(date(2026, 10, 14), 'Dag')
    entries = [{'user_id': 1, 'name': 'Worker', 'start': end-timedelta(hours=1), 'end': end+timedelta(hours=1)}]
    assert hours(entries, begin, end, end)[0]['Uren'] == 1


def test_dst_and_week_month_boundaries():
    begin, end = period_bounds(date(2026, 3, 29), 'Dag')
    assert (end-begin).total_seconds()/3600 == 23
    begin, end = period_bounds(date(2026, 10, 25), 'Dag')
    assert (end-begin).total_seconds()/3600 == 25
    assert (period_bounds(date(2026, 10, 14), 'Week')[1]-period_bounds(date(2026, 10, 14), 'Week')[0]).days == 7
    assert period_bounds(date(2026, 12, 15), 'Maand')[1] == datetime(2026, 12, 31, 23, tzinfo=timezone.utc)


def test_active_entries_count_until_now():
    begin, end = period_bounds(date(2026, 10, 14), 'Dag')
    entries = [{'user_id': 1, 'name': 'Worker', 'start': begin, 'end': None}]
    assert hours(entries, begin, end, begin+timedelta(hours=3))[0]['Uren'] == 3
