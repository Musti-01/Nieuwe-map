import time
import pytest

from workforce.qr_clock import build_employee_code, verify_employee_code, build_store_code, verify_store_code, build_store_url, qr_svg


def test_employee_qr_rotates_expires_and_is_branch_bound(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "0123456789abcdef0123456789abcdef")
    first = build_employee_code(7, 3, 150.0)
    second = build_employee_code(7, 3, 165.0)
    assert first != second
    assert verify_employee_code(first, 3, 150.0)["user_id"] == 7
    assert verify_employee_code(first, 3, 165.0)["user_id"] == 7
    assert verify_employee_code(first, 3, 180.0) is None
    assert verify_employee_code(first, 4, 150.0) is None
    assert verify_employee_code(first + "x", 3, 150.0) is None


def test_qr_secret_required(monkeypatch):
    monkeypatch.delenv("SHIFTFLOW_QR_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        build_employee_code(1, 1)


def test_qr_svg_rendered_locally(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "0123456789abcdef0123456789abcdef")
    svg = qr_svg(build_employee_code(1, 1, time.time()))
    assert b"<svg" in svg
    assert b"</svg>" in svg



def test_store_qr_rotates_expires_and_is_branch_bound(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    first = build_store_code(3, 150.0)
    second = build_store_code(3, 165.0)
    assert first != second
    assert verify_store_code(first, 150.0)["branch_id"] == 3
    assert verify_store_code(first, 165.0)["branch_id"] == 3
    assert verify_store_code(first, 180.0) is None
    assert verify_store_code(first + "x", 150.0) is None


def test_store_qr_url_requires_https(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "x" * 32)
    monkeypatch.setenv("APP_BASE_URL", "https://shiftflow.example")
    code = build_store_code(3, 150.0)
    assert build_store_url(code).startswith("https://shiftflow.example?clock=")

    monkeypatch.setenv("APP_BASE_URL", "http://shiftflow.example")
    with pytest.raises(RuntimeError, match="HTTPS"):
        build_store_url(code)
