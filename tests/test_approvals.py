from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from workforce.models import Organization, Branch, Notification, ApprovalDecision
from workforce.service import Denied

@pytest.fixture
def application(api):
    password = 'Approval-test-password!'
    api.register('platform@example.test', 'Platform Owner', password)
    api.bootstrap('platform@example.test')
    pt = api.login('platform@example.test', password)
    owner = api.register('owner@example.test', 'Owner', password, 'Business', 'Any chain', 'Location', 'Example Street 1, 1000 Brussels', '+32 123456789')
    ot = api.login('owner@example.test', password)
    org = api.organizations(ot)[0]['id']
    branch = api.branches(ot)[0]['id']
    return dict(pt=pt, ot=ot, owner=owner, org=org, branch=branch)


def test_new_requests_pending_with_contact_fields(api, application):
    rows = api.applications(application['pt'])
    assert len(rows) == 2
    assert all(r['status'] == 'pending' for r in rows)
    assert {r['kind'] for r in rows} == {'organization', 'branch'}
    assert rows[0]['bedrijf'] == 'Business'
    assert rows[1]['vestiging'] == 'Location'
    assert rows[1]['adres'] == 'Example Street 1, 1000 Brussels'
    assert rows[1]['email'] == 'owner@example.test'
    assert rows[1]['telefoon'] == '+32 123456789'
    assert rows[1]['verantwoordelijke'] == 'Owner'


def test_pending_operations_and_role_assignment_denied(api, application):
    a = application
    for fn in [lambda: api.clock_in(a['ot'], a['branch']), lambda: api.clock_out(a['ot'], a['branch']), lambda: api.entries(a['ot'], a['branch']), lambda: api.entries(a['ot'], a['branch'], True), lambda: api.members(a['ot'], a['branch']), lambda: api.set_role(a['ot'], a['branch'], a['owner'], 'admin'), lambda: api.audit(a['ot'], a['branch']), lambda: api.lookup_user(a['ot'], a['branch'], 'owner@example.test')]:
        with pytest.raises(Denied, match='goedgekeurd'):
            fn()


def test_both_approvals_required_then_operational(api, application):
    a = application
    with pytest.raises(ValueError, match='eerst de organisatie'):
        api.decide(a['pt'], 'branch', a['branch'], 'approve')
    api.decide(a['pt'], 'organization', a['org'], 'approve')
    with pytest.raises(Denied):
        api.clock_in(a['ot'], a['branch'])
    api.decide(a['pt'], 'branch', a['branch'], 'approve')
    assert api.clock_in(a['ot'], a['branch'])
    assert api.clock_out(a['ot'], a['branch'])
    api.set_role(a['ot'], a['branch'], a['owner'], 'admin')


def test_owner_cannot_approve_or_delegate(api, application):
    a = application
    for fn in [lambda: api.applications(a['ot']), lambda: api.decisions(a['ot']), lambda: api.decide(a['ot'], 'organization', a['org'], 'approve'), lambda: api.delegate_platform(a['ot'], 'owner@example.test', True), lambda: api.platform_users(a['ot'])]:
        with pytest.raises(Denied):
            fn()
    assert not api.identity(a['ot'])['platform_admin']


def test_explicit_delegation_and_immediate_revoke(api, application):
    a = application
    api.register('delegate@example.test', 'Delegate', 'Approval-test-password!')
    dt = api.login('delegate@example.test', 'Approval-test-password!')
    with pytest.raises(Denied):
        api.applications(dt)
    api.delegate_platform(a['pt'], 'delegate@example.test', True)
    api.decide(dt, 'organization', a['org'], 'approve')
    with pytest.raises(Denied):
        api.delegate_platform(dt, 'owner@example.test', True)
    api.delegate_platform(a['pt'], 'delegate@example.test', False)
    with pytest.raises(Denied):
        api.decide(dt, 'branch', a['branch'], 'approve')
    with pytest.raises(Denied):
        api.delegate_platform(a['pt'], 'platform@example.test', False)


def test_branch_admin_never_platform_authority(api, team):
    api.set_role(team['ot'], team['branch'], team['worker'], 'admin')
    with pytest.raises(Denied):
        api.applications(team['wt'])
    with pytest.raises(Denied):
        api.decide(team['wt'], 'branch', team['other_branch'], 'block', 'attempt')
    with pytest.raises(Denied):
        api.delegate_platform(team['wt'], 'worker@example.test', True)
    with pytest.raises(ValueError):
        api.set_role(team['wt'], team['branch'], team['worker'], 'platform_admin')


def test_rejection_recorded_and_rejected_unusable(api, application):
    a = application
    decision = api.decide(a['pt'], 'organization', a['org'], 'reject', 'Registration incomplete')
    rows = api.decisions(a['pt'])
    assert rows[0]['id'] == decision
    assert rows[0]['beoordelaar'] == 'platform@example.test'
    assert rows[0]['tijd']
    assert rows[0]['reden'] == 'Registration incomplete'
    assert rows[0]['naar'] == 'rejected'
    with api.sessions() as s:
        org = s.get(Organization, a['org'])
        assert org.reviewed_by == api.identity(a['pt'])['id']
        assert org.reviewed_at == rows[0]['tijd']
        assert s.scalar(select(Notification)).recipient == 'owner@example.test'
    with pytest.raises(Denied):
        api.clock_in(a['ot'], a['branch'])
    with pytest.raises(ValueError):
        api.decide(a['pt'], 'organization', a['org'], 'approve')


def test_block_and_reactivate_organization_and_branch(api, team):
    org = api.organizations(team['ot'])[0]['id']
    for kind, target in [('branch', team['branch']), ('organization', org)]:
        api.decide(team['pt'], kind, target, 'block', 'Owner requested pause')
        with pytest.raises(Denied):
            api.clock_in(team['wt'], team['branch'])
        with pytest.raises(Denied):
            api.members(team['ot'], team['branch'])
        api.decide(team['pt'], kind, target, 'reactivate')
        assert api.clock_in(team['wt'], team['branch'])
        api.clock_out(team['wt'], team['branch'])
    assert len(api.decisions(team['pt'])) == 8


def test_extra_branch_requires_own_approval(api, team):
    org = api.organizations(team['ot'])[0]['id']
    branch = api.add_branch(team['ot'], org, 'New', 'New address')
    assert next(b for b in api.branches(team['ot']) if b['id'] == branch)['status'] == 'pending'
    with pytest.raises(Denied):
        api.set_role(team['ot'], branch, team['worker'], 'admin')
    api.decide(team['pt'], 'branch', branch, 'approve')
    api.set_role(team['ot'], branch, team['worker'], 'admin')
    assert api.members(team['wt'], branch)


def test_decision_validation_and_race(api, application):
    a = application
    with pytest.raises(ValueError):
        api.decide(a['pt'], 'organization', a['org'], 'reject')
    with pytest.raises(ValueError):
        api.decide(a['pt'], 'user', a['owner'], 'approve')
    def decide(action):
        try:
            return bool(api.decide(a['pt'], 'organization', a['org'], action, 'Race test'))
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(decide, ['approve', 'reject'])) == 1
    assert len(api.decisions(a['pt'])) == 1
    with api.sessions() as s:
        assert len(list(s.scalars(select(Notification)))) == 1


def test_block_closes_active_entries_and_preserves_history(api, team):
    api.clock_in(team['wt'], team['branch'])
    api.decide(team['pt'], 'organization', api.organizations(team['ot'])[0]['id'], 'block', 'Temporarily closed')
    with pytest.raises(Denied):
        api.clock_out(team['wt'], team['branch'])
    api.decide(team['pt'], 'organization', api.organizations(team['ot'])[0]['id'], 'reactivate')
    assert api.entries(team['wt'], team['branch'])[0]['end'] is not None
    assert any(r['actie'] == 'clock.closed_by_block' for r in api.audit(team['ot'], team['branch']))
    assert api.clock_in(team['wt'], team['branch'])
