import streamlit as st
from streamlit.testing.v1 import AppTest


def app_for(token, engine, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', engine.url.render_as_string(hide_password=False))
    monkeypatch.delenv('AUTO_MIGRATE', raising=False)
    st.cache_resource.clear()
    app = AppTest.from_file('app.py', default_timeout=10)
    app.session_state['token'] = token
    return app.run()


def test_platform_navigation_and_owner_only_delegation(api, team, engine, monkeypatch):
    app = app_for(team['pt'], engine, monkeypatch)
    assert not app.exception
    assert any(s.value == 'Platformbeheer · Overzicht' for s in app.subheader)
    next(b for b in app.button if b.label == 'Naar aanvragen en blokkeringen').click().run()
    assert not app.exception
    assert any(s.label == 'Aanvraag beoordelen' for s in app.selectbox)
    app.radio(key='platform_page').set_value('Platformbeheerders').run()
    assert any(b.label == 'Machtiging opslaan' for b in app.button)
    assert not app.exception
    api.delegate_platform(team['pt'], 'worker@example.test', True)
    delegated = app_for(team['wt'], engine, monkeypatch)
    assert 'Platformbeheerders' not in delegated.radio(key='platform_page').options


def test_employee_shift_history_after_clock_out(api, team, engine, monkeypatch):
    api.clock_in(team['wt'], team['branch'])
    api.clock_out(team['wt'], team['branch'])
    app = app_for(team['wt'], engine, monkeypatch)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ['In- en uitklokken', 'Mijn shiften', 'Planning', 'Meldingen']
    assert len(app.dataframe) == 1
    assert app.dataframe[0].value.iloc[0]['Status'] == 'Wacht op controle'
    assert all(r.label != 'Platformonderdeel' for r in app.radio)
    next(b for b in app.button if b.label == 'Shiften verversen').click().run()
    assert not app.exception


def test_branch_admin_still_has_dashboard_team_and_audit(api, team, engine, monkeypatch):
    app = app_for(team['ot'], engine, monkeypatch)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ['In- en uitklokken', 'Mijn shiften', 'Dashboard', 'Shiften controleren', 'Team & rechten', 'Auditlog', 'Planning', 'Meldingen']
    assert any(b.label == 'Gebruiker zoeken' for b in app.button)


def test_admin_approves_shift_from_review_tab(api, team, engine, monkeypatch):
    api.clock_in(team['wt'], team['branch'])
    api.clock_out(team['wt'], team['branch'])
    app = app_for(team['ot'], engine, monkeypatch)
    assert not app.exception
    next(b for b in app.button if b.label == 'Shiftactie bevestigen').click().run()
    assert not app.exception
    assert api.entries(team['wt'],team['branch'])[0]['review_status'] == 'approved'


def test_owner_deactivates_employee_from_user_page(api,team,engine,monkeypatch):
    app=app_for(team['pt'],engine,monkeypatch)
    app.radio(key='platform_page').set_value('Gebruikers').run()
    assert not app.exception
    next(s for s in app.selectbox if s.label=='Account beheren').set_value(team['worker']).run()
    next(i for i in app.text_input if i.label=='Reden voor accountwijziging').set_value('Contract ended')
    next(c for c in app.checkbox if c.label.startswith('Ik bevestig')).check()
    next(b for b in app.button if b.label=='Account deactiveren').click().run()
    assert not app.exception
    assert next(u for u in api.accounts(team['pt']) if u['id']==team['worker'])['actief'] is False


def test_admin_plans_employee_shift_and_employee_sees_it(api,team,engine,monkeypatch):
    app=app_for(team['ot'],engine,monkeypatch)
    next(s for s in app.selectbox if s.label=='Medewerker inplannen').set_value(team['worker'])
    next(b for b in app.button if b.label=='Planning opslaan').click().run()
    assert not app.exception
    assert len(api.plans(team['wt'],team['branch']))==1
    worker=app_for(team['wt'],engine,monkeypatch)
    assert not worker.exception
    assert any(t.label=='Planning' for t in worker.tabs)
    assert not any(b.label=='Planning opslaan' for b in worker.button)


def test_invitation_creates_new_personal_account_through_ui(api,team,engine,monkeypatch):
    from urllib.parse import parse_qs,urlsplit
    monkeypatch.setenv('APP_BASE_URL','https://shiftflow.example')
    link=api.invite(team['ot'],team['branch'],'invite-ui@example.test')
    monkeypatch.setenv('DATABASE_URL',engine.url.render_as_string(hide_password=False))
    st.cache_resource.clear()
    app=AppTest.from_file('app.py',default_timeout=10)
    app.query_params['invite']=parse_qs(urlsplit(link).query)['invite'][0]
    app.run()
    next(x for x in app.text_input if x.label=='Jouw volledige naam').set_value('Invited Worker')
    next(x for x in app.text_input if x.label.startswith('Kies een wachtwoord')).set_value('New-password-123!')
    next(x for x in app.text_input if x.label=='Herhaal gekozen wachtwoord').set_value('New-password-123!')
    next(b for b in app.button if b.label=='Uitnodiging accepteren').click().run()
    assert not app.exception
    token=api.login('invite-ui@example.test','New-password-123!')
    assert api.branches(token)[0]['id']==team['branch']
