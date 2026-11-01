import time
import pytest

from workforce.qr_clock import build_employee_code, verify_employee_code, qr_svg


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
    assert "<svg" in svg
    assert "</svg>" in svg
