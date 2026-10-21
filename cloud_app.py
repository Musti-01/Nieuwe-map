"""Streamlit Community Cloud entrypoint. Values belong in the hosting secret UI."""
import os
import runpy
from pathlib import Path
import streamlit as st
from cloud_bootstrap import prepare_release, startup_error

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
    prepare_release(Path(__file__).parent)
    runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
except Exception as exc:
    reference = startup_error(exc)
    st.error(f'De app kon niet starten. Probeer opnieuw of geef deze foutcode door: {reference}')
    st.stop()
