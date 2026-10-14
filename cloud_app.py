"""Streamlit Community Cloud entrypoint. Values belong in the hosting secret UI."""
import os
import runpy
from pathlib import Path
import streamlit as st

try:
    for key in ('DATABASE_URL', 'APP_TIMEZONE'):
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
except FileNotFoundError:
    pass  # Local development can use an ignored .env instead.
os.environ['AUTO_MIGRATE'] = '1'
runpy.run_path(str(Path(__file__).with_name('app.py')), run_name='__main__')
