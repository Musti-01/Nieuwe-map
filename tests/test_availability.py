from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pytest

from workforce.service import Denied, now


TZ = ZoneInfo("Europe/Brussels")


def _tomorrow(hour=9):
    day = now().astimezone(TZ).date() + timedelta(days=1)
    return datetime.combine(day, datetime.strptime(f"{hour:02d}:00", "%H:%M").time(), tzinfo=TZ)


def test_employee_availability_crud_and_manager_visibility(api, team):
    start = _tomorrow(9)
    end = _tomorrow(17)
    aid = api.save_availability(team["wt"], team["branch"], start, end)
    own = api.availability_rules(team["wt"], team["branch"])
    assert own[0]["id"] == aid
    team_rows = api.availability_rules(team["ot"], team["branch"], team=True)
    assert any(r["user_id"] == team["worker"] for r in team_rows)

    with pytest.raises(Denied):
        api.delete_availability(team["ot"], team["branch"], aid, own[0]["version"])

    updated_start = _tomorrow(10)
    api.save_availability(
        team["wt"], team["branch"], updated_start, end,
        availability_id=aid, version=own[0]["version"],
    )
    updated = api.availability_rules(team["wt"], team["branch"])[0]
    assert updated["start"].astimezone(TZ).hour == 10

    assert api.delete_availability(team["wt"], team["branch"], aid, updated["version"])
    assert api.availability_rules(team["wt"], team["branch"]) == []


def test_weekly_availability_expands_and_prevents_overlap(api, team):
    start = _tomorrow(9)
    end = _tomorrow(17)
    until = start.date() + timedelta(weeks=3)
    api.save_availability(team["wt"], team["branch"], start, end, True, until)

    occurrences = api.availability_occurrences(
        team["wt"],
        team["branch"],
        start - timedelta(days=1),
        datetime.combine(until + timedelta(days=1), datetime.max.time(), tzinfo=TZ),
    )
    assert len(occurrences) == 4

    with pytest.raises(ValueError, match="overlapt"):
        api.save_availability(
            team["wt"],
            team["branch"],
            _tomorrow(12),
            _tomorrow(18),
        )


def test_availability_conflict_warnings_and_planning_candidates(api, team):
    start = _tomorrow(9)
    end = _tomorrow(17)
    api.save_availability(team["wt"], team["branch"], start, end)
    plan_start = _tomorrow(10)
    plan_end = _tomorrow(14)

    before = api.planning_candidates(team["ot"], team["branch"], plan_start, plan_end)
    worker = next(r for r in before if r["id"] == team["worker"])
    assert worker["available"]
    assert not worker["shift_conflict"]
    assert not worker["absence_conflict"]

    api.save_plan(team["ot"], team["branch"], team["worker"], plan_start, plan_end)
    api.request_absence(team["wt"], team["branch"], "sick", plan_start.date(), plan_start.date())

    slots = api.availability_occurrences(
        team["ot"],
        team["branch"],
        start - timedelta(hours=1),
        end + timedelta(hours=1),
        team=True,
    )
    slot = next(r for r in slots if r["user_id"] == team["worker"])
    assert slot["shift_conflict"]
    assert slot["absence_conflict"]

    after = api.planning_candidates(team["ot"], team["branch"], plan_start, plan_end)
    worker = next(r for r in after if r["id"] == team["worker"])
    assert worker["available"]
    assert worker["shift_conflict"]
    assert worker["absence_conflict"]


def test_availability_is_branch_isolated(api, team):
    start = _tomorrow(9)
    end = _tomorrow(17)
    api.save_availability(team["wt"], team["branch"], start, end)
    with pytest.raises(Denied):
        api.availability_rules(team["xt"], team["branch"], team=True)
