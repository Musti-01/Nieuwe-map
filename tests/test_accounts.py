from clock_helpers import planned_clock_in
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit
import re
import pytest
from sqlalchemy import select
from workforce.models import Notification, AccountToken, AuthSession
from workforce.service import Denied, now


def test_invitation_new_account_single_use_and_expiry(api,team,monkeypatch):
    monkeypatch.setenv('APP_BASE_URL','https://shiftflow.example')
    link=api.invite(team['ot'],team['branch'],'new@example.test')
    raw=parse_qs(urlsplit(link).query)['invite'][0]
    uid=api.accept_invite(raw,name='New worker',password='New-password-123!')
    token=api.login('new@example.test','New-password-123!')
    assert api.branches(token)[0]['id']==team['branch']
    assert not api.identity(token)['platform_admin']
    with pytest.raises(Denied):
        api.accept_invite(raw,token)
    with api.sessions() as s:
        assert s.scalar(select(AccountToken)).token_hash!=raw
    expired=parse_qs(urlsplit(api.invite(team['ot'],team['branch'],'late@example.test')).query)['invite'][0]
    with api.sessions.begin() as s:
        for row in s.scalars(select(AccountToken).where(AccountToken.email=='late@example.test')):
            row.expires_at=now()-timedelta(seconds=1)
    with pytest.raises(Denied):
        api.accept_invite(expired,name='Late',password='New-password-123!')


def test_invitation_authority_and_existing_identity(api,team,monkeypatch):
    monkeypatch.setenv('APP_BASE_URL','https://shiftflow.example')
    with pytest.raises(Denied):
        api.invite(team['wt'],team['branch'],'new@example.test')
    raw=parse_qs(urlsplit(api.invite(team['ot'],team['branch'],'worker@example.test')).query)['invite'][0]
    with pytest.raises(Denied):
        api.accept_invite(raw,team['xt'])
    assert api.accept_invite(raw,team['wt'])==team['worker']
    assert next(m['role'] for m in api.members(team['ot'],team['branch']) if m['id']==team['worker'])=='employee'
    raw=parse_qs(urlsplit(api.invite(team['ot'],team['branch'],'other-new@example.test')).query)['invite'][0]
    api.decide(team['pt'],'branch',team['branch'],'block','Closed')
    with pytest.raises(Denied):
        api.accept_invite(raw,name='New',password='New-password-123!')


def test_reset_is_generic_one_use_revokes_sessions_and_clears_lock(api,team,monkeypatch):
    monkeypatch.setenv('APP_BASE_URL','https://shiftflow.example')
    monkeypatch.setenv('EMAIL_DELIVERY_ENABLED','1')
    assert api.request_password_reset('missing@example.test') is True
    assert api.request_password_reset('worker@example.test') is True
    with api.sessions() as s:
        body=s.scalar(select(Notification.body).where(Notification.recipient=='worker@example.test'))
    raw=parse_qs(urlsplit(re.search(r'https://\S+',body).group()).query)['reset'][0]
    assert api.reset_password(raw,'Changed-password-123!')
    with pytest.raises(Denied):
        api.identity(team['wt'])
    with pytest.raises(Denied):
        api.login('worker@example.test','Correct-test-password!')
    assert api.login('worker@example.test','Changed-password-123!')
    with pytest.raises(Denied):
        api.reset_password(raw,'Another-password-123!')


def test_reset_without_mail_and_expired_link(api,team,monkeypatch):
    monkeypatch.delenv('EMAIL_DELIVERY_ENABLED',raising=False)
    with pytest.raises(ValueError,match='nog niet ingesteld'):
        api.request_password_reset('worker@example.test')
    monkeypatch.setenv('EMAIL_DELIVERY_ENABLED','1')
    monkeypatch.setenv('APP_BASE_URL','https://shiftflow.example')
    api.request_password_reset('worker@example.test')
    with api.sessions.begin() as s:
        s.scalar(select(AccountToken)).expires_at=now()-timedelta(seconds=1)
        body=s.scalar(select(Notification.body).where(Notification.recipient=='worker@example.test'))
    raw=parse_qs(urlsplit(re.search(r'https://\S+',body).group()).query)['reset'][0]
    with pytest.raises(Denied):
        api.reset_password(raw,'Changed-password-123!')


def test_change_password_requires_current_and_revokes_all_sessions(api,team):
    with pytest.raises(Denied):
        api.change_password(team['wt'],'wrong','Changed-password-123!')
    assert api.change_password(team['wt'],'Correct-test-password!','Changed-password-123!')
    with pytest.raises(Denied):
        api.identity(team['wt'])
    assert api.login('worker@example.test','Changed-password-123!')


def test_account_deactivation_enforces_access_and_closes_shift(api,team):
    planned_clock_in(api, team['wt'],team['branch'])
    with pytest.raises(Denied):
        api.set_account_active(team['ot'],team['worker'],False,'Left')
    assert api.set_account_active(team['pt'],team['worker'],False,'Left')
    with pytest.raises(Denied):
        api.identity(team['wt'])
    with pytest.raises(Denied):
        api.login('worker@example.test','Correct-test-password!')
    assert api.entries(team['ot'],team['branch'],True)[0]['end']
    with pytest.raises(Denied):
        api.set_account_active(team['pt'],api.identity(team['pt'])['id'],False,'Self')
    with pytest.raises(Denied):
        api.set_account_active(team['pt'],team['owner'],False,'Owner')
    assert api.set_account_active(team['pt'],team['worker'],True,'Returned')
    fresh=api.login('worker@example.test','Correct-test-password!')
    assert api.entries(fresh,team['branch'])


def test_invitation_requires_trusted_public_url(api,team,monkeypatch):
    for invalid in ['', 'http://example.test', 'https://example.test?evil=1']:
        monkeypatch.setenv('APP_BASE_URL',invalid)
        with pytest.raises(ValueError):
            api.invite(team['ot'],team['branch'],'new@example.test')
