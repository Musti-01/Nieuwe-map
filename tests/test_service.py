from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import pytest
from sqlalchemy import select, update
from workforce.models import User, AuthSession, WorkEntry, Membership
from workforce.service import Denied, now, digest


def test_registration_hash_and_login(api, engine):
    uid = api.register('Owner@Example.test', 'Owner', 'Strong-password-123', 'Org', 'Any Chain', 'Branch', 'Testadres 1', '+32 000000000')
    with api.sessions() as s:
        user = s.get(User, uid)
        assert user.password_hash.startswith('$argon2id$')
        assert 'Strong-password-123' not in user.password_hash
        assert not user.platform_admin
    token = api.login('owner@example.test', 'Strong-password-123')
    assert api.identity(token)['id'] == uid
    assert len(api.branches(token)) == 1
    assert len(api.organizations(token)) == 1


def test_weak_password_and_atomic_registration(api):
    with pytest.raises(ValueError):
        api.register('a@example.test', 'A', 'short', 'Org', 'Chain', 'Branch')
    with pytest.raises(ValueError):
        api.register('a@example.test', 'A', 'Strong-password-123', 'Org', '', 'Branch')
    assert api.register('a@example.test', 'A', 'Strong-password-123')
    with pytest.raises(ValueError):
        api.register('A@example.test', 'A', 'Strong-password-123')


def test_invalid_credentials_and_rate_limit(api):
    api.register('a@example.test', 'A', 'Strong-password-123')
    for _ in range(5):
        with pytest.raises(Denied, match='Ongeldige'):
            api.login('a@example.test', 'wrong')
    with pytest.raises(Denied, match='Te veel'):
        api.login('a@example.test', 'Strong-password-123')


def test_sessions_expire_and_logout(api, team):
    api.logout(team['wt'])
    with pytest.raises(Denied):
        api.identity(team['wt'])
    with api.sessions.begin() as s:
        s.execute(update(AuthSession).where(AuthSession.token_hash == digest(team['ot'])).values(expires_at=now()-timedelta(seconds=1)))
    with pytest.raises(Denied):
        api.branches(team['ot'])
    with pytest.raises(Denied):
        api.identity('invented-token')


def test_branch_isolation_all_operations(api, team):
    assert [b['id'] for b in api.branches(team['wt'])] == [team['branch']]
    other = team['other_branch']
    for action in [lambda: api.entries(team['wt'], other), lambda: api.members(team['ot'], other), lambda: api.clock_in(team['wt'], other), lambda: api.clock_out(team['wt'], other), lambda: api.audit(team['ot'], other), lambda: api.lookup_user(team['ot'], other, 'other@example.test'), lambda: api.set_role(team['ot'], other, team['worker'], 'admin')]:
        with pytest.raises(Denied):
            action()
    with pytest.raises(Denied):
        api.add_branch(team['wt'], api.organizations(team['ot'])[0]['id'], 'Hacked', 'Testadres')


def test_employee_cannot_self_promote_or_read_team(api, team):
    with pytest.raises(Denied):
        api.set_role(team['wt'], team['branch'], team['worker'], 'admin')
    with pytest.raises(Denied):
        api.entries(team['wt'], team['branch'], team=True)
    with pytest.raises(Denied):
        api.members(team['wt'], team['branch'])


def test_owner_grants_multi_branch_admin_and_revokes_immediately(api, team):
    new = api.add_branch(team['ot'], api.organizations(team['ot'])[0]['id'], 'Second', 'Testadres 2')
    api.decide(team['pt'], 'branch', new, 'approve')
    for branch in [team['branch'], new]:
        api.set_role(team['ot'], branch, team['worker'], 'admin')
        assert api.members(team['wt'], branch)
    api.set_role(team['ot'], new, team['worker'], 'employee')
    with pytest.raises(Denied):
        api.members(team['wt'], new)
    assert api.members(team['wt'], team['branch'])
    api.set_role(team['ot'], team['branch'], team['worker'], None)
    with pytest.raises(Denied):
        api.entries(team['wt'], team['branch'])
    assert len(api.branches(team['wt'])) == 1


def test_admin_can_assign_employee_but_not_admin(api, team):
    api.set_role(team['ot'], team['branch'], team['worker'], 'admin')
    new = api.register('new@example.test', 'New', 'Strong-password-123')
    api.set_role(team['wt'], team['branch'], new, 'employee')
    assert any(m['id'] == new for m in api.members(team['wt'], team['branch']))
    with pytest.raises(Denied):
        api.set_role(team['wt'], team['branch'], new, 'admin')
    with pytest.raises(Denied):
        api.set_role(team['wt'], team['branch'], team['owner'], None)


def test_clock_lifecycle_and_history_isolation(api, team):
    entry = api.clock_in(team['wt'], team['branch'])
    with api.sessions.begin() as s:
        s.execute(update(WorkEntry).where(WorkEntry.id == entry).values(started_at=now()-timedelta(hours=2)))
    assert api.entries(team['ot'], team['branch']) == []
    assert len(api.entries(team['ot'], team['branch'], team=True)) == 1
    api.clock_out(team['wt'], team['branch'])
    e = api.entries(team['wt'], team['branch'])[0]
    assert 2 <= (e['end']-e['start']).total_seconds()/3600 < 2.01
    with pytest.raises(ValueError):
        api.clock_out(team['wt'], team['branch'])
    events = api.audit(team['ot'], team['branch'])
    assert {'clock.in', 'clock.out', 'membership.changed'} <= {a['actie'] for a in events}
    api.set_role(team['ot'], team['branch'], team['worker'], None)
    assert len(api.entries(team['ot'], team['branch'], team=True)) == 1


def test_global_active_session_uniqueness(api, team):
    api.set_role(team['xt'], team['other_branch'], team['worker'], 'employee')
    api.clock_in(team['wt'], team['branch'])
    with pytest.raises(ValueError, match='actieve'):
        api.clock_in(team['wt'], team['other_branch'])
    with pytest.raises(ValueError):
        api.set_role(team['ot'], team['branch'], team['worker'], None)
    api.clock_out(team['wt'], team['branch'])
    assert api.clock_in(team['wt'], team['other_branch'])


def test_concurrent_clock_in_one_winner(api, team):
    api.set_role(team['xt'], team['other_branch'], team['worker'], 'employee')
    def clock(branch):
        try:
            api.clock_in(team['wt'], branch)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(clock, [team['branch'], team['other_branch']])) == 1


def test_bootstrap_once_and_not_public_signup(api):
    api.register('owner@example.test', 'Owner', 'Strong-password-123')
    api.register('other@example.test', 'Other', 'Strong-password-123')
    token = api.login('owner@example.test', 'Strong-password-123')
    other_token = api.login('other@example.test', 'Strong-password-123')
    api.bootstrap('owner@example.test')
    assert api.identity(token)['platform_admin']
    assert api.identity(token)['platform_owner']
    with pytest.raises(ValueError, match='gesloten'):
        api.bootstrap('other@example.test')
    assert not api.identity(other_token)['platform_admin']
