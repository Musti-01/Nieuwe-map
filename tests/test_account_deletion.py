import pytest
from sqlalchemy import select
from workforce.models import User,Membership,AuthSession,Audit
from workforce.service import Denied


def test_unused_account_deleted_with_sessions_and_links(api,team):
    assert next(u for u in api.accounts(team['pt']) if u['id']==team['worker'])['can_delete']
    assert api.delete_unused_account(team['pt'],team['worker'])
    with api.sessions() as s:
        assert s.get(User,team['worker']) is None
        assert s.scalar(select(Membership).where(Membership.user_id==team['worker'])) is None
        assert s.scalar(select(AuthSession).where(AuthSession.user_id==team['worker'])) is None
        assert s.scalar(select(Audit).where(Audit.action=='account.deleted'))
    with pytest.raises(Denied):
        api.identity(team['wt'])


def test_history_prevents_deletion_but_keeps_deactivation(api,team):
    api.clock_in(team['wt'],team['branch'])
    api.clock_out(team['wt'],team['branch'])
    row=next(u for u in api.accounts(team['pt']) if u['id']==team['worker'])
    assert row['can_manage'] and not row['can_delete']
    with pytest.raises(Denied,match='historiek'):
        api.delete_unused_account(team['pt'],team['worker'])
    assert api.entries(team['wt'],team['branch'])
    assert api.set_account_active(team['pt'],team['worker'],False,'Left')


def test_owner_self_and_nonplatform_protected(api,team):
    owner_id=api.identity(team['pt'])['id']
    for uid in [owner_id,team['owner']]:
        with pytest.raises(Denied):
            api.delete_unused_account(team['pt'],uid)
    with pytest.raises(Denied):
        api.delete_unused_account(team['ot'],team['worker'])
    with pytest.raises(Denied):
        api.delete_unused_account(team['wt'],team['worker'])
    policy=next(u for u in api.accounts(team['pt']) if u['id']==owner_id)
    assert not policy['can_manage'] and not policy['can_delete']


def test_planning_prevents_deletion(api,team):
    from datetime import timedelta
    from workforce.service import now
    start=now()+timedelta(days=1)
    api.save_plan(team['ot'],team['branch'],team['worker'],start,start+timedelta(hours=4))
    with pytest.raises(Denied):
        api.delete_unused_account(team['pt'],team['worker'])
    assert api.plans(team['wt'],team['branch'])


def test_pending_invitation_blocks_deletion_and_keeps_link_valid(api,team,monkeypatch):
    monkeypatch.setenv('APP_BASE_URL','https://shiftflow.example')
    api.invite(team['ot'],team['branch'],'worker@example.test')
    with pytest.raises(Denied):
        api.delete_unused_account(team['pt'],team['worker'])
    assert api.identity(team['wt'])['id']==team['worker']


def test_clock_in_vs_deletion_never_discards_a_work_entry(api,team):
    from concurrent.futures import ThreadPoolExecutor
    def clock():
        try:
            return bool(api.clock_in(team['wt'],team['branch']))
        except (Denied,ValueError):
            return False
    def remove():
        try:
            return api.delete_unused_account(team['pt'],team['worker'])
        except (Denied,ValueError):
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        a=pool.submit(clock)
        b=pool.submit(remove)
        clocked,deleted=a.result(),b.result()
    assert clocked != deleted
    if clocked:
        assert api.entries(team['ot'],team['branch'],True)
