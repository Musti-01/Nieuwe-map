"""Streamlit Community Cloud entrypoint. Values belong in the hosting secret UI."""
import os
import runpy
from pathlib import Path
import streamlit as st

try:
    for key in ('DATABASE_URL', 'APP_TIMEZONE', 'APP_BASE_URL', 'EMAIL_DELIVERY_ENABLED',
                'RESEND_API_KEY', 'MAIL_FROM', 'SMTP_HOST', 'SMTP_PORT', 'SMTP_USER',
                'SMTP_PASSWORD', 'SICK_NOTE_RETENTION_DAYS'):
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
except FileNotFoundError:
    pass  # Local development can use an ignored .env instead.
os.environ['AUTO_MIGRATE'] = '1'
try:
    runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
except Exception as exc:
    from workforce.db import make_engine, sessions
    from workforce.operations import report_error
    from workforce.i18n import tr
    reference = report_error(sessions(make_engine()), exc)
    st.error(tr('Er ging iets mis. Probeer opnieuw of geef deze foutcode door: {v0}', v0=reference))
    st.stop()
