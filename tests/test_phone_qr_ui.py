from datetime import timedelta
import streamlit as st
from streamlit.testing.v1 import AppTest

from workforce.qr_store import build_store_code
from workforce.service import now


def test_manager_store_qr_page_renders(api, team, engine, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("APP_BASE_URL", "https://shiftflow.example")
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)
    st.cache_resource.clear()

    app = AppTest.from_file("app.py", default_timeout=10)
    app.session_state["token"] = team["ot"]
    app.run()
    app.radio(key=f"branch_page_{team['branch']}").set_value("QR inklokken").run()

    assert not app.exception
    assert any("Medewerkers scannen hem met hun eigen gsm" in x.value for x in app.markdown)
    assert any("<svg" in x.value for x in app.markdown)


def test_phone_scan_query_clocks_employee_in(api, team, engine, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", engine.url.render_as_string(hide_password=False))
    monkeypatch.setenv("APP_BASE_URL", "https://shiftflow.example")
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    monkeypatch.delenv("AUTO_MIGRATE", raising=False)

    start = now()
    api.save_plan(team["ot"], team["branch"], team["worker"], start, start + timedelta(hours=2), "UI phone scan")

    st.cache_resource.clear()
    app = AppTest.from_file("app.py", default_timeout=10)
    app.session_state["token"] = team["wt"]
    app.query_params["clock"] = build_store_code(team["branch"])
    app.run()

    assert not app.exception
    entries = api.entries(team["wt"], team["branch"])
    assert len(entries) == 1
    assert entries[0]["end"] is None
