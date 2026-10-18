"""Provision scheduled shifts for tests focused on reviews, accounts and isolation.

Clock-policy tests call Service.clock_in directly; this helper never bypasses it.
Schedule creation/overlap permissions are exercised separately by test_planning.
"""
from datetime import timedelta
from workforce.models import ShiftPlan
from workforce.service import now


def planned_clock_in(api, token, branch_id, plan_id=None):
    if plan_id is None:
        with api.sessions.begin() as s:
            actor = api._actor(s, token)
            api._access(s, actor, branch_id)
            plan = ShiftPlan(branch_id=branch_id, user_id=actor.id,
                             starts_at=now(), ends_at=now()+timedelta(hours=1),
                             note='', status='scheduled', version=1, created_by=actor.id)
            s.add(plan)
            s.flush()
            plan_id=plan.id
    return api.clock_in(token, branch_id, plan_id)
