import pytest
from workforce.qr_clock import build_code, verify_code, scanner_authorized


def test_qr_rotates_and_expires(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_QR_SECRET", "0123456789abcdef0123456789abcdef")
    a = build_code(7, 3, 150.0)
    b = build_code(7, 3, 165.0)
    assert a != b
    assert verify_code(a, 3, 150.0) == 7
    assert verify_code(a, 3, 165.0) == 7
    assert verify_code(a, 3, 180.0) is None
    assert verify_code(a, 4, 150.0) is None
    assert verify_code(a + "x", 3, 150.0) is None


def test_scanner_key(monkeypatch):
    monkeypatch.setenv("SHIFTFLOW_SCANNER_KEY", "A" * 40)
    assert scanner_authorized("A" * 40)
    assert not scanner_authorized("bad")


def test_missing_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("SHIFTFLOW_QR_SECRET", raising=False)
    with pytest.raises(RuntimeError):
        build_code(1, 1)
