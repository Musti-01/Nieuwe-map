from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import pytest
from workforce.clock_policy import clock_in_allowed
from workforce.service import Denied

TZ=ZoneInfo('Europe/Brussels')
START=datetime(2020,5,4,16,tzinfo=TZ)


def plan_at(api,team,monkeypatch,start=START,end=None):
    monkeypatch.setenv('APP_TIMEZONE','Europe/Brussels')
    monkeypatch.setattr('workforce.service.now',lambda:start-timedelta(hours=2))
    return api.save_plan(team['ot'],team['branch'],team['worker'],start,end or start+timedelta(hours=4))


@pytest.mark.parametrize('offset,allowed',[(-601,False),(-600,True),(-1,True),(0,True),(60,True),(14399,True),(14400,False)])
def test_server_clock_window(api,team,monkeypatch,offset,allowed):
    plan=plan_at(api,team,monkeypatch)
    current=START+timedelta(seconds=offset)
    monkeypatch.setattr('workforce.service.now',lambda:current)
    if allowed:
        eid=api.clock_in(team['wt'],team['branch'],plan)
        assert api.entries(team['wt'],team['branch'])[0]['start']==current
        assert eid
    else:
        with pytest.raises(ValueError,match='10 minuten'):
            api.clock_in(team['wt'],team['branch'],plan)
        assert api.entries(team['wt'],team['branch'])==[]


def test_no_plan_cancelled_other_person_and_reuse(api,team,monkeypatch):
    plan=plan_at(api,team,monkeypatch)
    monkeypatch.setattr('workforce.service.now',lambda:START)
    with pytest.raises(ValueError,match='ingeplande'):
        api.clock_in(team['wt'],team['branch'])
    with pytest.raises(Denied):
        api.clock_in(team['ot'],team['branch'],plan)
    api.clock_in(team['wt'],team['branch'],plan)
    monkeypatch.setattr('workforce.service.now',lambda:START+timedelta(days=1))
    # Clocking OUT remains possible after the scheduled day and end time.
    api.clock_out(team['wt'],team['branch'])
    with pytest.raises(ValueError,match='al een tijdregistratie'):
        api.clock_in(team['wt'],team['branch'],plan)


def test_cancelled_and_other_branch_plans_denied(api,team,monkeypatch):
    plan=plan_at(api,team,monkeypatch)
    api.cancel_plan(team['ot'],team['branch'],plan,1,'Changed')
    monkeypatch.setattr('workforce.service.now',lambda:START)
    with pytest.raises(Denied):
        api.clock_in(team['wt'],team['branch'],plan)
    with pytest.raises(Denied):
        api.clock_in(team['xt'],team['other_branch'],plan)


@pytest.mark.parametrize('start,current,allowed',[
    (datetime(2020,5,5,0,5,tzinfo=TZ),datetime(2020,5,4,23,59,tzinfo=TZ),False),
    (datetime(2020,5,5,0,5,tzinfo=TZ),datetime(2020,5,5,0,0,tzinfo=TZ),True),
    (datetime(2020,5,4,23,30,tzinfo=TZ),datetime(2020,5,5,0,0,tzinfo=TZ),False),
])
def test_midnight_policy_enforced_by_server(api,team,monkeypatch,start,current,allowed):
    plan=plan_at(api,team,monkeypatch,start,start+timedelta(hours=4))
    monkeypatch.setattr('workforce.service.now',lambda:current)
    if allowed:
        assert api.clock_in(team['wt'],team['branch'],plan)
    else:
        with pytest.raises(ValueError,match='begindag'):
            api.clock_in(team['wt'],team['branch'],plan)


def test_timezone_and_dst_boundaries():
    start=datetime(2026,10,25,1,5,tzinfo=timezone.utc) # second 02:05 after the autumn clock change
    assert clock_in_allowed(start,start+timedelta(hours=2),start-timedelta(minutes=10),TZ)
    assert not clock_in_allowed(start,start+timedelta(hours=2),start-timedelta(minutes=10,seconds=1),TZ)


def test_ui_enables_clock_in_at_boundary_and_keeps_clock_out_available(api,team,engine,monkeypatch):
    from test_ui import app_for
    plan=plan_at(api,team,monkeypatch)
    current=[START-timedelta(minutes=10,seconds=1)]
    monkeypatch.setattr('workforce.service.now',lambda:current[0])
    app=app_for(team['wt'],engine,monkeypatch)
    assert not app.exception
    assert next(b for b in app.button if b.label=='Inklokken').disabled
    assert not any(s.label=='Inklokken voor' for s in app.selectbox)
    current[0]=START-timedelta(minutes=10)
    next(b for b in app.button if b.label=='Inklokmogelijkheden verversen').click().run()
    assert not app.exception
    assert not next(b for b in app.button if b.label=='Inklokken').disabled
    next(b for b in app.button if b.label=='Inklokken').click().run()
    assert not app.exception
    assert api.entries(team['wt'],team['branch'])[0]['plan_id']==plan
    current[0]=START+timedelta(days=1)
    next(b for b in app.button if b.label=='Inklokmogelijkheden verversen').click().run()
    assert not next(b for b in app.button if b.label=='Uitklokken').disabled
    next(b for b in app.button if b.label=='Uitklokken').click().run()
    assert not app.exception
    assert api.entries(team['wt'],team['branch'])[0]['end']==current[0]
