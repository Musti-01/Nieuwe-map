from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
import pytest
from workforce.service import Denied, now
from workforce.models import WorkEntry


def closed(api, team):
    eid = api.clock_in(team['wt'], team['branch'])
    with api.sessions.begin() as s:
        s.get(WorkEntry,eid).started_at = now()-timedelta(hours=2)
    api.clock_out(team['wt'],team['branch'])
    return api.entries(team['wt'],team['branch'])[0]


def test_approve_correct_reapprove_history_keeps_original(api, team):
    e=closed(api,team)
    assert e['review_status']=='pending'
    api.review_shift(team['ot'],team['branch'],e['id'],e['version'],'approve')
    approved=api.entries(team['wt'],team['branch'])[0]
    assert approved['review_status']=='approved'
    assert approved['reviewed_by']==team['owner']
    end=e['end']-timedelta(hours=1)
    api.review_shift(team['ot'],team['branch'],e['id'],approved['version'],'correct','Werk stopte een uur eerder',e['start'],end)
    corrected=api.entries(team['wt'],team['branch'])[0]
    assert corrected['review_status']=='pending'
    assert corrected['reviewed_by'] is None
    assert corrected['end']==end
    history=api.shift_history(team['wt'],team['branch'],e['id'])
    assert history[0]['oud_einde']==e['end']
    assert history[0]['nieuw_einde']==end
    assert history[0]['reden']=='Werk stopte een uur eerder'
    api.review_shift(team['ot'],team['branch'],e['id'],corrected['version'],'approve')
    assert len(api.shift_history(team['ot'],team['branch'],e['id']))==3


def test_employee_and_other_branch_have_no_review_authority(api,team):
    e=closed(api,team)
    for token,branch in [(team['wt'],team['branch']),(team['xt'],team['branch']),(team['xt'],team['other_branch'])]:
        with pytest.raises(Denied):
            api.review_shift(token,branch,e['id'],e['version'],'approve')
    with pytest.raises(Denied):
        api.shift_history(team['xt'],team['other_branch'],e['id'])
    other=api.register('new@example.test','New','Strong-password-123')
    api.set_role(team['ot'],team['branch'],other,'employee')
    token=api.login('new@example.test','Strong-password-123')
    with pytest.raises(Denied):
        api.shift_history(token,team['branch'],e['id'])


def test_no_self_approval_or_correction(api,team):
    api.set_role(team['ot'],team['branch'],team['worker'],'admin')
    e=closed(api,team)
    for action in ['approve','correct']:
        with pytest.raises(Denied,match='andere'):
            api.review_shift(team['wt'],team['branch'],e['id'],e['version'],action,'Self',e['start'],e['end'])


def test_active_cannot_be_approved_but_admin_can_close_with_reason(api,team):
    eid=api.clock_in(team['wt'],team['branch'])
    e=api.entries(team['wt'],team['branch'])[0]
    with pytest.raises(ValueError,match='lopende'):
        api.review_shift(team['ot'],team['branch'],eid,e['version'],'approve')
    api.review_shift(team['ot'],team['branch'],eid,e['version'],'correct','Vergeten uit te klokken',e['start'],now())
    with pytest.raises(ValueError):
        api.clock_out(team['wt'],team['branch'])
    assert api.entries(team['wt'],team['branch'])[0]['review_status']=='pending'
    assert api.clock_in(team['wt'],team['branch'])


def test_validate_reason_timezones_future_and_overlap(api,team):
    e=closed(api,team)
    with api.sessions.begin() as s:
        s.get(WorkEntry,e['id']).ended_at=now()-timedelta(minutes=30)
    e=api.entries(team['wt'],team['branch'])[0]
    args=(team['ot'],team['branch'],e['id'],e['version'],'correct')
    for reason,start,end in [('',e['start'],e['end']),('test',e['start'].replace(tzinfo=None),e['end']),('test',e['start'],now()+timedelta(hours=1)),('test',e['end'],e['start'])]:
        with pytest.raises(ValueError):
            api.review_shift(*args,reason,start,end)
    second=api.clock_in(team['wt'],team['branch'])
    with api.sessions.begin() as s:
        s.get(WorkEntry,second).started_at=e['end']+timedelta(seconds=1)
    api.clock_out(team['wt'],team['branch'])
    # Extend first shift into the second shift.
    with pytest.raises(ValueError,match='overlappen'):
        api.review_shift(*args,'Overlap',e['start'],now())


def test_stale_review_and_concurrent_approval_one_winner(api,team):
    e=closed(api,team)
    def approve(_):
        try:
            return bool(api.review_shift(team['ot'],team['branch'],e['id'],e['version'],'approve'))
        except ValueError:
            return False
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(approve,range(2)))==1
    assert len(api.shift_history(team['wt'],team['branch'],e['id']))==1
