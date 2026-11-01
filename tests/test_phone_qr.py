from datetime import timedelta
import time
import pytest

from workforce.qr_store import build_scan_url, build_store_code, verify_store_code, qr_svg
from workforce.service import Denied, now

SECRET = "x" * 32


def _plan_now(api, team):
    start = now()
    return api.save_plan(
        team["ot"],
        team["branch"],
        team["worker"],
        start,
        start + timedelta(hours=2),
        "Phone QR test",
    )


def test_store_qr_rotates_expires_and_rejects_tampering(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    first = build_store_code(3, 150.0)
    second = build_store_code(3, 165.0)
    assert first != second
    assert verify_store_code(first, 150.0)["branch_id"] == 3
    assert verify_store_code(first, 165.0)["branch_id"] == 3
    assert verify_store_code(first, 180.0) is None
    assert verify_store_code(first + "x", 150.0) is None


def test_store_scan_url_requires_https(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    monkeypatch.setenv("APP_BASE_URL", "https://shiftflow.example")
    code = build_store_code(4)
    assert build_scan_url(code).startswith("https://shiftflow.example?clock=")
    assert b"<svg" in qr_svg(build_scan_url(code))

    monkeypatch.setenv("APP_BASE_URL", "http://shiftflow.example")
    with pytest.raises(RuntimeError, match="HTTPS"):
        build_scan_url(code)


def test_employee_phone_scan_clocks_in_and_replay_is_blocked(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    _plan_now(api, team)
    code = build_store_code(team["branch"])

    result = api.phone_qr_clock_in(team["wt"], code)
    assert result["branch_id"] == team["branch"]
    assert result["entry_id"]
    assert api.entries(team["wt"], team["branch"])[0]["end"] is None

    with pytest.raises(Denied, match="al gebruikt"):
        api.phone_qr_clock_in(team["wt"], code)

    assert api.clock_out(team["wt"], team["branch"])


def test_phone_scan_requires_membership_valid_qr_and_planned_shift(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)

    with pytest.raises(ValueError, match="Geen geldige ingeplande shift"):
        api.phone_qr_clock_in(team["wt"], build_store_code(team["branch"]))

    _plan_now(api, team)

    with pytest.raises(Denied):
        api.phone_qr_clock_in(team["wt"], build_store_code(team["other_branch"]))

    expired = build_store_code(team["branch"], time.time() - 90)
    with pytest.raises(Denied, match="ongeldig"):
        api.phone_qr_clock_in(team["wt"], expired)


def test_old_direct_clock_in_path_stays_closed(api, team):
    with pytest.raises(Denied, match="gsm"):
        api.clock_in(team["wt"], team["branch"])
