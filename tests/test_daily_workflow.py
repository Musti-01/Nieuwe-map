from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from clock_helpers import planned_clock_in
from test_ui import app_for
from workforce.service import now
from workforce.clock_policy import clock_in_opens_at, clock_in_allowed


def test_owner_today_planning_keeps_other_branches_and_cancelled_shifts_out(api,team,engine,monkeypatch):
    current=datetime(2020,5,4,12,tzinfo=timezone.utc)
    monkeypatch.setattr('workforce.service.now',lambda:current)
    api.save_plan(team['ot'],team['branch'],team['worker'],current+timedelta(minutes=5),current+timedelta(hours=1))
    cancel=api.save_plan(team['ot'],team['branch'],team['owner'],current+timedelta(hours=2),current+timedelta(hours=3))
    api.cancel_plan(team['ot'],team['branch'],cancel,1,'Not needed')
    api.save_plan(team['xt'],team['other_branch'],team['other'],current+timedelta(minutes=5),current+timedelta(hours=1))
    app=app_for(team['ot'],engine,monkeypatch)
    assert not app.exception
    table=app.dataframe[0].value
    assert list(table['Medewerker'])==['Worker']
    assert list(table['Status'])==['Kan nu inklokken']
    assert any('04-05-2020' in c.value for c in app.caption)


def test_overview_shortcut_opens_the_requested_shift_and_approves_it(api,team,engine,monkeypatch):
    old=planned_clock_in(api,team['wt'],team['branch'])
    api.clock_out(team['wt'],team['branch'])
    second=api.register('second@example.test','Second','Strong-password-123')
    api.set_role(team['ot'],team['branch'],second,'employee')
    token=api.login('second@example.test','Strong-password-123')
    recent=planned_clock_in(api,token,team['branch'])
    api.clock_out(token,team['branch'])
    app=app_for(team['ot'],engine,monkeypatch)
    app.button(key=f'home_review_{old}').click().run()
    assert not app.exception
    assert app.selectbox(key=f"review_entry_{team['branch']}").value==old
    next(b for b in app.button if b.label=='Shiftactie bevestigen').click().run()
    assert not app.exception
    entries={e['id']:e for e in api.entries(team['ot'],team['branch'],team=True)}
    assert entries[old]['review_status']=='approved'
    assert entries[recent]['review_status']=='pending'


def test_alert_shortcut_opens_active_shift_for_correction(api,team,engine,monkeypatch):
    entry=planned_clock_in(api,team['wt'],team['branch'])
    future=now()+timedelta(hours=2)
    monkeypatch.setattr('workforce.service.now',lambda:future)
    app=app_for(team['ot'],engine,monkeypatch)
    app.radio(key=f"branch_page_{team['branch']}").set_value('Meldingen').run()
    app.button(key=f'alert_review_{entry}').click().run()
    assert not app.exception
    assert app.selectbox(key=f"review_status_{team['branch']}").value=='Bezig'
    assert app.selectbox(key=f"review_entry_{team['branch']}").value==entry
    assert next(s for s in app.selectbox if s.label=='Shiftactie').options==['Corrigeren']


def test_foreign_shift_focus_does_not_leak_employee_details(api,team,engine,monkeypatch):
    foreign=planned_clock_in(api,team['xt'],team['other_branch'])
    app=app_for(team['ot'],engine,monkeypatch)
    app.session_state[f"focus_review_{team['branch']}"]=foreign
    app.radio(key=f"branch_page_{team['branch']}").set_value('Shiften controleren').run()
    assert not app.exception
    assert any('niet meer beschikbaar' in i.value for i in app.info)
    assert not any(s.label=='Shift selecteren' for s in app.selectbox)


def test_employee_next_shift_and_midnight_opening_are_explicit(api,team,engine,monkeypatch):
    tz=ZoneInfo('Europe/Brussels')
    start=datetime(2020,5,5,0,5,tzinfo=tz)
    current=start-timedelta(hours=2)
    monkeypatch.setattr('workforce.service.now',lambda:current)
    api.save_plan(team['ot'],team['branch'],team['worker'],start,start+timedelta(hours=4))
    app=app_for(team['wt'],engine,monkeypatch)
    assert not app.exception
    assert any('Volgende shift: 05-05-2020 00:05' in i.value for i in app.info)
    assert any('Inklokken mogelijk vanaf 05-05-2020 00:00' in m.value for m in app.markdown)
    assert next(b for b in app.button if b.label=='Inklokken').disabled


def test_existing_employee_shortcut_and_planning_date(api,team,engine,monkeypatch):
    app=app_for(team['ot'],engine,monkeypatch)
    app.button(key='manager_open_Medewerkers toevoegen').click().run()
    next(b for b in app.button if b.label=='Bestaande medewerker koppelen').click().run()
    assert not app.exception
    assert any(b.label=='Gebruiker zoeken' for b in app.button)
    app.radio(key=f"branch_page_{team['branch']}").set_value('Planning').run()
    future=datetime.now(ZoneInfo('Europe/Brussels')).date()+timedelta(days=3)
    next(d for d in app.date_input if d.label=='Datum voor planning').set_value(future).run()
    assert not app.exception
    assert next(d for d in app.date_input if d.label=='Geplande begindatum').value==future
    assert next(e for e in app.expander if e.label=='Shift toevoegen of wijzigen').proto.expanded


def test_clock_window_uses_real_minutes_across_autumn_clock_change():
    tz=ZoneInfo('Europe/Brussels')
    start=datetime(2026,10,25,2,5,tzinfo=tz,fold=1)
    opening=clock_in_opens_at(start,tz)
    assert opening==datetime(2026,10,25,0,55,tzinfo=timezone.utc)
    assert clock_in_allowed(start,start+timedelta(hours=3),opening,tz)
    assert not clock_in_allowed(start,start+timedelta(hours=3),opening-timedelta(seconds=1),tz)
