from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from workforce.shift_view import shift_rows


def test_shift_view_clips_selection_not_full_duration_and_labels_active():
    tz = ZoneInfo('Europe/Brussels')
    begin = datetime(2026, 10, 14, tzinfo=timezone.utc)
    end = datetime(2026, 10, 15, tzinfo=timezone.utc)
    entries = [
        {'start': datetime(2026, 10, 13, 23, tzinfo=timezone.utc), 'end': datetime(2026, 10, 14, 2, tzinfo=timezone.utc)},
        {'start': datetime(2026, 10, 14, 10, tzinfo=timezone.utc), 'end': None},
        {'start': datetime(2026, 10, 15, 1, tzinfo=timezone.utc), 'end': None},
    ]
    snapshot = datetime(2026, 10, 14, 11, tzinfo=timezone.utc)
    rows = shift_rows(entries, begin, end, tz, snapshot)
    assert len(rows) == 2
    assert rows[0]['Ingeklokt'] == '14-10-2026 01:00'
    assert rows[0]['Duur volledige shift (uur)'] == 3
    assert rows[0]['Status'] == 'Wacht op controle'
    assert rows[1]['Status'] == 'Bezig'
    assert rows[1]['Uitgeklokt'] == 'Nog bezig'
    assert rows[1]['Duur volledige shift (uur)'] == 1


def test_empty_shift_view():
    moment = datetime(2026, 10, 14, tzinfo=timezone.utc)
    assert shift_rows([], moment, moment, ZoneInfo('Europe/Brussels'), moment) == []
