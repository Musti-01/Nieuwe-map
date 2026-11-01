from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from zoneinfo import ZoneInfo
import time
import pytest

from workforce.qr_clock import build_employee_code
from workforce.service import Denied, now


SECRET = "0123456789abcdef0123456789abcdef"


def _plan_now(api, team):
    start = now()
    return api.save_plan(
        team["ot"],
        team["branch"],
        team["worker"],
        start,
        start + timedelta(hours=2),
        "Scanner test",
    )


def test_scanner_clock_in_success_replay_and_direct_path_blocked(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    device = api.create_scanner(team["ot"], team["branch"], "Kassa tablet")
    info = api.scanner_info(device["token"])
    assert info["branch_id"] == team["branch"]

    _plan_now(api, team)
    code = build_employee_code(team["worker"], team["branch"])
    result = api.scanner_clock_in(device["token"], code)
    assert result["user_id"] == team["worker"]
    assert result["name"] == "Worker"
    assert api.entries(team["wt"], team["branch"])[0]["end"] is None

    with pytest.raises(Denied, match="alleen via"):
        api.clock_in(team["wt"], team["branch"], result["entry_id"])

    with pytest.raises(Denied, match="al gebruikt"):
        api.scanner_clock_in(device["token"], code)

    api.clock_out(team["wt"], team["branch"])
    assert api.entries(team["wt"], team["branch"])[0]["end"] is not None


def test_scanner_rejects_wrong_branch_expired_and_revoked(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    device = api.create_scanner(team["ot"], team["branch"], "Scanner 1")
    _plan_now(api, team)

    wrong_branch = build_employee_code(team["worker"], team["other_branch"])
    with pytest.raises(Denied, match="ongeldig"):
        api.scanner_clock_in(device["token"], wrong_branch)

    expired = build_employee_code(team["worker"], team["branch"], time.time() - 90)
    with pytest.raises(Denied, match="ongeldig"):
        api.scanner_clock_in(device["token"], expired)

    api.revoke_scanner(team["ot"], team["branch"], device["id"])
    with pytest.raises(Denied, match="niet geautoriseerd"):
        api.scanner_info(device["token"])


def test_scanner_keeps_absence_and_shift_controls(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    device = api.create_scanner(team["ot"], team["branch"], "Scanner 1")
    _plan_now(api, team)
    today = now().astimezone(ZoneInfo("Europe/Brussels")).date()
    api.request_absence(team["wt"], team["branch"], "sick", today, today)

    code = build_employee_code(team["worker"], team["branch"])
    with pytest.raises(ValueError, match="afwezig"):
        api.scanner_clock_in(device["token"], code)


def test_same_qr_concurrent_scan_has_one_winner(api, team, monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", SECRET)
    device = api.create_scanner(team["ot"], team["branch"], "Scanner concurrent")
    _plan_now(api, team)
    code = build_employee_code(team["worker"], team["branch"])

    def scan(_):
        try:
            api.scanner_clock_in(device["token"], code)
            return True
        except (ValueError, Denied):
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(scan, [1, 2])) == 1


def test_scanner_pairing_url_requires_https(api, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://shiftflow.example")
    url = api.scanner_pairing_url("A" * 40)
    assert url.startswith("https://shiftflow.example?scanner=")

    monkeypatch.setenv("APP_BASE_URL", "http://shiftflow.example")
    with pytest.raises(ValueError, match="HTTPS"):
        api.scanner_pairing_url("A" * 40)
