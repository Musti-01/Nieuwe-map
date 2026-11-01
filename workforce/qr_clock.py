"""Secure rotating employee QR codes for scanner-only clock-in."""
import base64
import hashlib
import hmac
import io
import os
import time

WINDOW_SECONDS = 15
PREFIX = "sfq2"
STORE_PREFIX = "sfs1"


def _key():
    secret = os.getenv("SHIFTFLOW_QR_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SHIFTFLOW_QR_SECRET moet minimaal 32 tekens bevatten.")
    return secret.encode("utf-8")


def _signature(user_id, branch_id, window):
    payload = f"shiftflow:employee:v2:{int(user_id)}:{int(branch_id)}:{int(window)}".encode()
    raw = hmac.new(_key(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw[:20]).decode().rstrip("=")


def build_employee_code(user_id, branch_id, timestamp=None):
    timestamp = time.time() if timestamp is None else float(timestamp)
    window = int(timestamp) // WINDOW_SECONDS
    return f"{PREFIX}.{int(user_id)}.{int(branch_id)}.{window}.{_signature(user_id, branch_id, window)}"


def verify_employee_code(value, expected_branch_id=None, timestamp=None):
    """Return token data for a current/previous-window QR, otherwise None."""
    timestamp = time.time() if timestamp is None else float(timestamp)
    if not isinstance(value, str) or len(value) > 220:
        return None
    parts = value.strip().split(".")
    if len(parts) != 5 or parts[0] != PREFIX:
        return None
    try:
        user_id = int(parts[1])
        branch_id = int(parts[2])
        window = int(parts[3])
    except (ValueError, OverflowError):
        return None
    if user_id <= 0 or branch_id <= 0:
        return None
    if expected_branch_id is not None and branch_id != int(expected_branch_id):
        return None
    current = int(timestamp) // WINDOW_SECONDS
    if window not in (current, current - 1):
        return None
    if not hmac.compare_digest(parts[4], _signature(user_id, branch_id, window)):
        return None
    return {"user_id": user_id, "branch_id": branch_id, "window": window}


def qr_svg(value):
    """Render locally; the rotating credential never leaves ShiftFlow."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError as exc:
        raise RuntimeError("De qrcode-package ontbreekt. Installeer de projectrequirements opnieuw.") from exc
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=9,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    return output.getvalue()


def _store_signature(branch_id, window):
    payload = f"shiftflow:store:v1:{int(branch_id)}:{int(window)}".encode()
    raw = hmac.new(_key(), payload, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw[:20]).decode().rstrip("=")


def build_store_code(branch_id, timestamp=None):
    timestamp = time.time() if timestamp is None else float(timestamp)
    window = int(timestamp) // WINDOW_SECONDS
    return f"{STORE_PREFIX}.{int(branch_id)}.{window}.{_store_signature(branch_id, window)}"


def verify_store_code(value, timestamp=None):
    """Return branch/window for a current or immediately previous store QR window."""
    timestamp = time.time() if timestamp is None else float(timestamp)
    if not isinstance(value, str) or len(value) > 180:
        return None
    parts = value.strip().split(".")
    if len(parts) != 4 or parts[0] != STORE_PREFIX:
        return None
    try:
        branch_id = int(parts[1])
        window = int(parts[2])
    except (ValueError, OverflowError):
        return None
    if branch_id <= 0:
        return None
    current = int(timestamp) // WINDOW_SECONDS
    if window not in (current, current - 1):
        return None
    if not hmac.compare_digest(parts[3], _store_signature(branch_id, window)):
        return None
    return {"branch_id": branch_id, "window": window}


def build_store_url(code, base_url=None):
    from urllib.parse import urlencode
    base = (base_url or os.getenv("APP_BASE_URL", "")).strip().rstrip("/")
    if not base.startswith("https://"):
        raise RuntimeError("APP_BASE_URL moet een publiek HTTPS-adres zijn.")
    return base + "?" + urlencode({"clock": code})
