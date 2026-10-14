import os
import pytest
from sqlalchemy import text
from sqlalchemy.engine import make_url
from alembic import command
from alembic.config import Config
from workforce.db import make_engine, sessions
from workforce.service import Service

@pytest.fixture(scope="session")
def engine():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not (make_url(url).database or '').endswith('_test'):
        pytest.exit("TEST_DATABASE_URL moet naar een afzonderlijke database eindigend op _test wijzen.", returncode=2)
    previous = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = url
    command.upgrade(Config('alembic.ini'), 'head')
    if previous is None:
        os.environ.pop('DATABASE_URL')
    else:
        os.environ['DATABASE_URL'] = previous
    engine = make_engine(url)
    yield engine
    engine.dispose()

@pytest.fixture
def api(engine):
    with engine.begin() as connection:
        connection.execute(text('TRUNCATE shift_reviews, notifications, approval_decisions, audit_events, auth_sessions, login_limits, work_entries, memberships, branches, organizations, users RESTART IDENTITY CASCADE'))
    return Service(sessions(engine))

@pytest.fixture
def team(api):
    password = 'Correct-test-password!'
    api.register('platform@example.test', 'Platform', password)
    api.bootstrap('platform@example.test')
    platform_token = api.login('platform@example.test', password)
    owner = api.register('owner@example.test', 'Owner', password, 'Org A', 'Chain A', 'Branch A', 'Teststraat 1, Brussel', '+32 000000001')
    owner_token = api.login('owner@example.test', password)
    branch = api.branches(owner_token)[0]['id']
    worker = api.register('worker@example.test', 'Worker', password)
    worker_token = api.login('worker@example.test', password)
    api.decide(platform_token, 'organization', api.organizations(owner_token)[0]['id'], 'approve')
    api.decide(platform_token, 'branch', branch, 'approve')
    api.set_role(owner_token, branch, worker, 'employee')
    other = api.register('other@example.test', 'Other', password, 'Org B', 'Chain B', 'Branch B', 'Teststraat 2, Brussel', '+32 000000002')
    other_token = api.login('other@example.test', password)
    api.decide(platform_token, 'organization', api.organizations(other_token)[0]['id'], 'approve')
    api.decide(platform_token, 'branch', api.branches(other_token)[0]['id'], 'approve')
    return dict(pt=platform_token, owner=owner, ot=owner_token, worker=worker, wt=worker_token, branch=branch, other=other, xt=other_token, other_branch=api.branches(other_token)[0]['id'])
