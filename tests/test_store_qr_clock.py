from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
import time
import pytest

from workforce.qr_clock import build_store_code
from workforce.service import Denied, now


def _plan_now(api, team):
    start = now()
    return api.save_plan(
        team["ot"],
        team["branch"],
        team["worker"],
        start,
        start + timedelta(hours=2),
        "Store QR test",
    )


def test_employee_scans_store_qr_and_clocks_in(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    _plan_now(api, team)
    code = build_store_code(team["branch"])

    result = api.store_qr_clock_in(team["wt"], code)

    assert result["branch_id"] == team["branch"]
    entry = api.entries(team["wt"], team["branch"])[0]
    assert entry["id"] == result["entry_id"]
    assert entry["end"] is None

    with pytest.raises(Denied, match="QR-code in de vestiging"):
        api.clock_in(team["wt"], team["branch"])

    assert api.clock_out(team["wt"], team["branch"])
    assert api.entries(team["wt"], team["branch"])[0]["end"] is not None


def test_store_qr_rejects_wrong_branch_tamper_and_expiry(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    _plan_now(api, team)

    other = build_store_code(team["other_branch"])
    with pytest.raises(Denied):
        api.store_qr_clock_in(team["wt"], other)

    tampered = build_store_code(team["branch"]) + "x"
    with pytest.raises(Denied, match="ongeldig"):
        api.store_qr_clock_in(team["wt"], tampered)

    expired = build_store_code(team["branch"], time.time() - 90)
    with pytest.raises(Denied, match="ongeldig"):
        api.store_qr_clock_in(team["wt"], expired)


def test_store_qr_keeps_absence_and_shift_controls(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    _plan_now(api, team)
    today = now().astimezone(ZoneInfo("Europe/Brussels")).date()
    api.request_absence(team["wt"], team["branch"], "sick", today, today)

    code = build_store_code(team["branch"])
    with pytest.raises(ValueError, match="afwezig"):
        api.store_qr_clock_in(team["wt"], code)


def test_same_store_qr_can_be_used_by_different_employees(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    second = api.register("second-store@example.test", "Second Store", "Strong-password-123!")
    api.set_role(team["ot"], team["branch"], second, "employee")
    second_token = api.login("second-store@example.test", "Strong-password-123!")

    start = now()
    api.save_plan(team["ot"], team["branch"], team["worker"], start, start + timedelta(hours=2), "A")
    api.save_plan(team["ot"], team["branch"], second, start, start + timedelta(hours=2), "B")
    code = build_store_code(team["branch"])

    assert api.store_qr_clock_in(team["wt"], code)["entry_id"]
    assert api.store_qr_clock_in(second_token, code)["entry_id"]


def test_store_qr_concurrent_scan_for_same_employee_only_clocks_once(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    _plan_now(api, team)
    code = build_store_code(team["branch"])

    def scan(_):
        try:
            api.store_qr_clock_in(team["wt"], code)
            return True
        except (ValueError, Denied):
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(scan, [1, 2])) == 1

    assert len(api.entries(team["wt"], team["branch"])) == 1
