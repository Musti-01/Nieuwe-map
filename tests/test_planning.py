from clock_helpers import planned_clock_in
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from workforce.models import WorkEntry, ShiftPlan
from workforce.service import now, Denied


def test_plan_lifecycle_permissions_and_actual_link(api,team):
    start=now();end=now()+timedelta(hours=2)
    with pytest.raises(Denied):
        api.save_plan(team['wt'],team['branch'],team['worker'],start,end)
    plan=api.save_plan(team['ot'],team['branch'],team['worker'],start,end,'Delivery')
    assert api.plans(team['wt'],team['branch'])[0]['id']==plan
    assert api.plans(team['ot'],team['branch'])==[]
    with pytest.raises(Denied):
        api.plans(team['wt'],team['branch'],True)
    with pytest.raises(Denied):
        api.plans(team['xt'],team['branch'])
    planned_clock_in(api, team['wt'],team['branch'],plan)
    assert api.plans(team['ot'],team['branch'],True)[0]['entry_id']
    with pytest.raises(ValueError):
        api.cancel_plan(team['ot'],team['branch'],plan,1,'Changed')
    api.clock_out(team['wt'],team['branch'])
    with pytest.raises(ValueError):
        api.clock_in(team['wt'],team['branch'],plan)


def test_plan_update_cancel_overlap_and_stale_version(api,team):
    start=now()+timedelta(days=1);end=start+timedelta(hours=4)
    plan=api.save_plan(team['ot'],team['branch'],team['worker'],start,end)
    with pytest.raises(ValueError,match='ingepland'):
        api.save_plan(team['ot'],team['branch'],team['worker'],start,end)
    api.save_plan(team['ot'],team['branch'],team['worker'],start,end+timedelta(hours=1),'Updated',plan,1)
    with pytest.raises(ValueError):
        api.cancel_plan(team['ot'],team['branch'],plan,1,'Stale')
    api.cancel_plan(team['ot'],team['branch'],plan,2,'No longer needed')
    assert api.plans(team['wt'],team['branch'])[0]['status']=='cancelled'
    assert api.save_plan(team['ot'],team['branch'],team['worker'],start,end)


def test_cross_branch_plan_overlap_serialized(api,team):
    api.set_role(team['xt'],team['other_branch'],team['worker'],'employee')
    start=now()+timedelta(days=1);end=start+timedelta(hours=4)
    def save(pair):
        token,branch=pair
        try:
            api.save_plan(token,branch,team['worker'],start,end)
            return True
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(save,[(team['ot'],team['branch']),(team['xt'],team['other_branch'])]))==1


def test_alerts_for_overdue_and_unplanned_long_shift(api,team,monkeypatch):
    # Historical unplanned registrations remain supported for clock-out/alerts.
    with api.sessions.begin() as s:
        entry=WorkEntry(branch_id=team['branch'],user_id=team['worker'],started_at=now()-timedelta(hours=13),review_status='pending',version=1)
        s.add(entry)
        s.flush()
        eid=entry.id
    assert api.alerts(team['wt'],team['branch'])[0]['type']=='uitklokken'
    api.clock_out(team['wt'],team['branch'])
    assert api.alerts(team['wt'],team['branch'])==[]
    assert api.alerts(team['ot'],team['branch'],True)[0]['type']=='controle'
    start=now();end=now()+timedelta(minutes=30)
    plan=api.save_plan(team['ot'],team['branch'],team['worker'],start,end)
    planned_clock_in(api, team['wt'],team['branch'],plan)
    monkeypatch.setattr('workforce.service.now',lambda:end+timedelta(minutes=20))
    assert any(a['type']=='uitklokken' for a in api.alerts(team['wt'],team['branch']))


def test_wrong_plan_membership_and_invalid_times(api,team):
    start=now()+timedelta(hours=1);end=start+timedelta(hours=4)
    with pytest.raises(ValueError):
        api.save_plan(team['ot'],team['branch'],team['other'],start,end)
    with pytest.raises(ValueError):
        api.save_plan(team['ot'],team['branch'],team['worker'],end,start)
    with pytest.raises(ValueError):
        api.save_plan(team['ot'],team['branch'],team['worker'],start.replace(tzinfo=None),end)
    with pytest.raises(Denied):
        api.clock_in(team['wt'],team['branch'],99999)
