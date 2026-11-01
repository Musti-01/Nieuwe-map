import pytest

from workforce.qr_station import (
    build_scan_url,
    build_station_code,
    verify_station_code,
)


def test_station_code_rotates_and_expires(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "0123456789abcdef0123456789abcdef")
    first = build_station_code(3, 150.0)
    second = build_station_code(3, 165.0)

    assert first != second
    assert verify_station_code(first, 3, 150.0)
    assert verify_station_code(first, 3, 165.0)
    assert not verify_station_code(first, 3, 180.0)


def test_station_code_is_branch_bound_and_tamper_resistant(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "0123456789abcdef0123456789abcdef")
    code = build_station_code(7, 150.0)

    assert verify_station_code(code, 7, 150.0)
    assert not verify_station_code(code, 8, 150.0)
    assert not verify_station_code(code + "x", 7, 150.0)


def test_scan_url(monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "https://shiftflow.example")
    assert build_scan_url("sfq1.3.10.signature") == (
        "https://shiftflow.example?clock=sfq1.3.10.signature"
    )


def test_missing_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("SHIFTFLOW_QR_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        build_station_code(1, 150.0)
