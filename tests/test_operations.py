from datetime import timedelta
from sqlalchemy import select
import pytest
from workforce.models import SickNote, SystemEvent
from workforce.operations import maintenance, report_error, record_event
from workforce.service import now, Denied
from test_sick_notes import attachment
from test_ui import app_for


def test_medical_access_delete_and_expiration(api, team):
    note = api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment())
    for token in (team['wt'], team['ot'], team['xt']):
        with pytest.raises(Denied):
            api.delete_sick_note(token, team['branch'], note)
    assert api.delete_sick_note(team['pt'], team['branch'], note)
    with api.sessions() as session:
        assert session.get(SickNote, note) is None
    note = api.upload_sick_note(team['wt'], team['branch'], 'brief.pdf', attachment())
    with api.sessions.begin() as session:
        session.get(SickNote, note).expires_at = now()-timedelta(seconds=1)
    with pytest.raises(Denied):
        api.download_sick_note(team['pt'], team['branch'], note)
    assert api.sick_notes(team['pt'], team['branch'], team=True) == []
    assert maintenance(api.sessions) == 1
    assert maintenance(api.sessions) == 0


def test_sanitized_errors_and_platform_status(api, team, caplog):
    reference = report_error(api.sessions, RuntimeError('SECRET reset=https://secret.example user@example.test'))
    assert 'SECRET' not in caplog.text and 'user@example.test' not in caplog.text
    assert reference in caplog.text
    with api.sessions() as session:
        events = list(session.scalars(select(SystemEvent)))
        assert len(events) == 1 and 'SECRET' not in events[0].code
    for token in (team['wt'], team['ot']):
        with pytest.raises(Denied):
            api.system_status(token)
    assert api.system_status(team['pt'])['last_backup'] is None
    record_event(api.sessions, 'backup', 'completed')
    assert api.system_status(team['pt'])['last_backup'] is not None


def test_system_status_screen(api, team, engine, monkeypatch):
    app = app_for(team['pt'], engine, monkeypatch)
    app.radio(key='platform_page').set_value('Systeemstatus').run()
    assert not app.exception
    assert any('geen geslaagde back-up' in w.value for w in app.warning)
