from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from workforce.service import Denied, now
from test_sick_notes import attachment
from workforce.models import SickNote
from test_ui import app_for


def test_leave_approval_conflicts_and_cancellation(api, team):
    start = now()+timedelta(days=2)
    day = start.astimezone(ZoneInfo('Europe/Brussels')).date()
    absence = api.request_absence(team['wt'], team['branch'], 'leave', day, day)
    assert api.absences(team['wt'], team['branch'])[0]['status'] == 'pending'
    assert api.absences(team['xt'], team['other_branch']) == []
    with pytest.raises(Denied):
        api.review_absence(team['wt'], team['branch'], absence, 'approve')
    with pytest.raises(Denied):
        api.review_absence(team['xt'], team['other_branch'], absence, 'approve')
    api.review_absence(team['ot'], team['branch'], absence, 'approve')
    with pytest.raises(ValueError, match='afwezig'):
        api.save_plan(team['ot'], team['branch'], team['worker'], start, start+timedelta(hours=1))
    api.review_absence(team['ot'], team['branch'], absence, 'cancel')
    assert api.save_plan(team['ot'], team['branch'], team['worker'], start, start+timedelta(hours=1))
    with pytest.raises(ValueError):
        api.review_absence(team['ot'], team['branch'], absence, 'approve')


def test_sick_note_link_and_retention(api, team, monkeypatch):
    monkeypatch.setenv('SICK_NOTE_RETENTION_DAYS', '14')
    day = now().date()
    note_id = api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment(), day, day+timedelta(days=2))
    absence = api.absences(team['wt'], team['branch'])[0]
    assert absence['kind'] == 'sick' and absence['status'] == 'approved'
    with api.sessions() as session:
        note = session.get(SickNote, note_id)
        assert note.absence_id == absence['id']
        assert (note.expires_at.date()-absence['end']).days in (14, 15)
    assert api.upload_sick_note(team['wt'], team['branch'], 'extra.pdf', attachment(), absence_id=absence['id'])
    with pytest.raises(Denied):
        api.upload_sick_note(team['ot'], team['branch'], 'extra.pdf', attachment(), absence_id=absence['id'])


def test_overlap_self_approval_and_pending_withdrawal(api, team):
    day = now().date()
    own = api.request_absence(team['ot'], team['branch'], 'leave', day, day)
    with pytest.raises(Denied):
        api.review_absence(team['ot'], team['branch'], own, 'approve')
    assert api.review_absence(team['ot'], team['branch'], own, 'cancel')
    api.request_absence(team['wt'], team['branch'], 'sick', day, day)
    with pytest.raises(ValueError, match='al een afwezigheid'):
        api.request_absence(team['wt'], team['branch'], 'leave', day, day)


def test_sick_blocks_clock_in_but_not_clock_out(api, team, monkeypatch):
    current = datetime(2026, 10, 21, 12, tzinfo=timezone.utc)
    monkeypatch.setattr('workforce.service.now', lambda: current)
    plan = api.save_plan(team['ot'], team['branch'], team['worker'], current, current+timedelta(hours=2))
    day = current.date()
    absence = api.request_absence(team['wt'], team['branch'], 'sick', day, day)
    with pytest.raises(ValueError, match='afwezig'):
        api.clock_in(team['wt'], team['branch'], plan)
    api.review_absence(team['ot'], team['branch'], absence, 'cancel')
    api.clock_in(team['wt'], team['branch'], plan)
    api.request_absence(team['wt'], team['branch'], 'sick', day, day)
    assert api.clock_out(team['wt'], team['branch'])


def test_absence_ui_and_planning_visibility(api, team, engine, monkeypatch):
    day = now().astimezone(ZoneInfo('Europe/Brussels')).date()
    absence = api.request_absence(team['wt'], team['branch'], 'leave', day, day)
    app = app_for(team['ot'], engine, monkeypatch)
    app.radio(key=f"branch_page_{team['branch']}").set_value('Afwezigheden').run()
    assert not app.exception
    app.button(key=f'absence_approve_{absence}').click().run()
    assert not app.exception
    assert api.absences(team['wt'], team['branch'])[0]['status'] == 'approved'
    app.radio(key=f"branch_page_{team['branch']}").set_value('Planning').run()
    assert not app.exception
    assert any(s.value == 'Afwezigheden in deze periode' for s in app.subheader)
    assert any('Worker' in str(d.value) and 'Verlof' in str(d.value) for d in app.dataframe)
