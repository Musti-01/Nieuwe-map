"""Exercise the actual hosted entrypoint in an isolated Python process."""
import os
import subprocess
import sys


def execute(script, engine):
    env = os.environ.copy()
    env['DATABASE_URL'] = engine.url.render_as_string(hide_password=False)
    env['EMAIL_DELIVERY_ENABLED'] = '0'
    result = subprocess.run([sys.executable, '-c', script], env=env, capture_output=True, text=True, timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr


def test_hosted_entrypoint_recovers_stale_models(engine):
    execute('''
import sys, types, threading
import workforce
from streamlit.testing.v1 import AppTest
old = types.ModuleType('workforce.models')
sys.modules['workforce.models'] = old
workforce.models = old
mail = types.ModuleType('workforce.mail')
stop = threading.Event()
mail._worker_stops = [stop]
sys.modules['workforce.mail'] = mail
app = AppTest.from_file('cloud_app.py', default_timeout=20).run()
assert not app.exception
assert not app.error
assert any(t.label == 'Inloggen' for t in app.tabs)
assert stop.is_set()
from workforce.models import Absence, SystemEvent
from cloud_bootstrap import prepare_release
assert prepare_release('.') is False
app.run()
assert not app.exception and not app.error
''', engine)


def test_startup_error_does_not_import_broken_application_or_expose_secrets(engine):
    execute('''
from unittest.mock import patch
import builtins
from streamlit.testing.v1 import AppTest
original = builtins.__import__
def broken(name, *args, **kwargs):
    if name.startswith('workforce'):
        raise ImportError('SECRET database-password reset-token')
    return original(name, *args, **kwargs)
with patch('builtins.__import__', side_effect=broken):
    app = AppTest.from_file('cloud_app.py', default_timeout=20).run()
assert not app.exception
assert len(app.error) == 1
assert 'foutcode' in app.error[0].value
assert 'SECRET' not in app.error[0].value
''', engine)
