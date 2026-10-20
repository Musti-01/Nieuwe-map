import pytest
from workforce.service import Denied
from test_ui import app_for


def test_accounts_group_members_and_owners_without_platform_access_leaking(api, team):
    accounts = {u['id']: u for u in api.accounts(team['pt'])}
    assert accounts[team['worker']]['branch_ids'] == [team['branch']]
    assert accounts[team['owner']]['branch_ids'] == [team['branch']]
    assert accounts[team['other']]['branch_ids'] == [team['other_branch']]
    assert accounts[api.identity(team['pt'])['id']]['branch_ids'] == []
    api.set_role(team['xt'], team['other_branch'], team['worker'], 'employee')
    assert next(u for u in api.accounts(team['pt']) if u['id'] == team['worker'])['branch_ids'] == sorted([team['branch'], team['other_branch']])
    api.set_role(team['ot'], team['branch'], team['worker'], None)
    assert next(u for u in api.accounts(team['pt']) if u['id'] == team['worker'])['branch_ids'] == [team['other_branch']]
    with pytest.raises(Denied):
        api.accounts(team['wt'])


def test_click_branch_shows_only_its_users_and_clears_selection(api, team, engine, monkeypatch):
    app = app_for(team['pt'], engine, monkeypatch)
    app.radio(key='platform_page').set_value('Gebruikers').run()
    assert not app.exception
    assert not any(str(b.key).startswith('manage_user_') for b in app.button)
    app.button(key=f"account_branch_{team['branch']}").click().run()
    assert not app.exception
    assert app.button(key=f"manage_user_{team['worker']}")
    assert not any(b.key == f"manage_user_{team['other']}" for b in app.button)
    app.button(key=f"manage_user_{team['worker']}").click().run()
    assert any(s.value == 'Account: Worker' for s in app.subheader)
    next(b for b in app.button if b.label == 'Terug naar vestigingen').click().run()
    app.button(key=f"account_branch_{team['other_branch']}").click().run()
    assert not app.exception
    assert app.button(key=f"manage_user_{team['other']}")
    assert not any(s.value == 'Account: Worker' for s in app.subheader)
    assert not any(b.key == f"manage_user_{team['worker']}" for b in app.button)
