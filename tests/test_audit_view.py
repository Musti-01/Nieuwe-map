from clock_helpers import planned_clock_in
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import pytest
from workforce.i18n import tr, set_language, catalogs
from workforce.ui_audit import audit_rows, ACTIONS, ROLES
from workforce.service import Denied


def test_audit_names_subjects_and_original_evidence(api,team):
    planned_clock_in(api, team['wt'],team['branch'])
    events=api.audit(team['ot'],team['branch'])
    clock=next(e for e in events if e['actie']=='clock.in')
    assert clock['actor_name']=='Worker'
    assert clock['subject']=='Worker'
    assert clock['detail'].startswith('entry=')
    approval=next(e for e in events if e['actie']=='approval.approve')
    assert approval['actor_name']=='Platform'
    assert approval['subject']=='Branch A'
    assert (approval['previous_status'],approval['status'])==('pending','approved')
    with pytest.raises(Denied):
        api.audit(team['wt'],team['branch'])
    with pytest.raises(Denied):
        api.audit(team['ot'],team['other_branch'])


@pytest.mark.parametrize('language',['nl','fr','en','de','es'])
def test_readable_audit_in_all_languages(language):
    set_language(language)
    try:
        event=dict(tijd=datetime(2026,10,15,19,17,tzinfo=timezone.utc),actor_name='Inloggen',actie='approval.approve',subject='Test',previous_status='pending',status='approved')
        row=audit_rows([event],ZoneInfo('Europe/Brussels'))[0]
        assert row[tr('Datum en tijd')]=='15-10-2026 21:17:00'
        assert row[tr('Uitgevoerd door')]=='Inloggen'
        assert row[tr('Gebeurtenis')]==tr('Vestiging goedgekeurd')
        assert row[tr('Toelichting')]==tr('In afwachting')+' → '+tr('Goedgekeurd')
        assert all('approval.approve' not in str(v) for v in row.values())
        assert all(v in catalogs() for v in [*ACTIONS.values(),*ROLES.values()])
    finally:
        set_language('nl')


def test_manager_audit_screen(api,team,engine,monkeypatch):
    from test_ui import app_for
    app=app_for(team['ot'],engine,monkeypatch)
    app.radio(key=f"branch_page_{team['branch']}").set_value('Auditlog').run()
    assert not app.exception
    table=app.dataframe[0].value
    row=table[table['Gebeurtenis']=='Vestiging goedgekeurd'].iloc[0]
    assert row['Uitgevoerd door']=='Platform'
    assert row['Gebeurtenis']=='Vestiging goedgekeurd'
    assert row['Betreft']=='Branch A'
    assert any('Technische gegevens' in e.label for e in app.expander)


def test_correction_history_shows_reason_and_original_times(api,team):
    from datetime import timedelta
    planned_clock_in(api, team['wt'],team['branch'])
    api.clock_out(team['wt'],team['branch'])
    entry=api.entries(team['wt'],team['branch'])[0]
    start=entry['start']-timedelta(minutes=10)
    end=entry['start']-timedelta(minutes=1)
    api.review_shift(team['ot'],team['branch'],entry['id'],entry['version'],'correct','Vergeten uitklokken',start,end)
    event=next(e for e in api.audit(team['ot'],team['branch']) if e['actie']=='shift.correct')
    assert event['old_start']==entry['start']
    assert event['new_start']==start
    assert event['subject']=='Worker'
    assert event['reason']=='Vergeten uitklokken'
    row=audit_rows([event],ZoneInfo('Europe/Brussels'))[0]
    assert row['Gebeurtenis']=='Werkuren gecorrigeerd'
    assert row['Toelichting'].endswith('Vergeten uitklokken')
    assert 'Van ' in row['Toelichting'] and ' naar ' in row['Toelichting']
