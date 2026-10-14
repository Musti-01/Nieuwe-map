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
    assert [tab.label for tab in app.tabs] == ['In- en uitklokken', 'Mijn shiften']
    assert len(app.dataframe) == 1
    assert app.dataframe[0].value.iloc[0]['Status'] == 'Wacht op controle'
    assert all(r.label != 'Platformonderdeel' for r in app.radio)
    next(b for b in app.button if b.label == 'Shiften verversen').click().run()
    assert not app.exception


def test_branch_admin_still_has_dashboard_team_and_audit(api, team, engine, monkeypatch):
    app = app_for(team['ot'], engine, monkeypatch)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ['In- en uitklokken', 'Mijn shiften', 'Dashboard', 'Shiften controleren', 'Team & rechten', 'Auditlog']
    assert any(b.label == 'Gebruiker zoeken' for b in app.button)


def test_admin_approves_shift_from_review_tab(api, team, engine, monkeypatch):
    api.clock_in(team['wt'], team['branch'])
    api.clock_out(team['wt'], team['branch'])
    app = app_for(team['ot'], engine, monkeypatch)
    assert not app.exception
    next(b for b in app.button if b.label == 'Shiftactie bevestigen').click().run()
    assert not app.exception
    assert api.entries(team['wt'],team['branch'])[0]['review_status'] == 'approved'
