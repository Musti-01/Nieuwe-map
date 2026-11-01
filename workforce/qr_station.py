"""Rotating, branch-bound QR credentials for in-store clock-in.

The QR is a short-lived proof that the employee saw the current code for a
specific branch. It is not, by itself, cryptographic proof of physical presence:
a screenshot can still be forwarded during the short validity window.
"""
import base64
import hashlib
import hmac
import io
import os
import time
from urllib.parse import quote

WINDOW_SECONDS = 15
_PREFIX = "sfq1"


def qr_enabled():
    return os.getenv("SHIFTFLOW_QR_ENABLED") == "1"


def _key():
    secret = os.getenv("SHIFTFLOW_QR_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SHIFTFLOW_QR_SECRET moet minimaal 32 tekens bevatten.")
    return secret.encode("utf-8")


def _signature(branch_id, window):
    message = f"shiftflow:station:v1:{int(branch_id)}:{int(window)}".encode()
    raw = hmac.new(_key(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw[:20]).decode().rstrip("=")


def build_station_code(branch_id, timestamp=None):
    timestamp = time.time() if timestamp is None else timestamp
    window = int(timestamp) // WINDOW_SECONDS
    return f"{_PREFIX}.{int(branch_id)}.{window}.{_signature(branch_id, window)}"


def verify_station_code(value, branch_id, timestamp=None):
    """Return True for a valid code from the current or previous time window."""
    timestamp = time.time() if timestamp is None else timestamp
    if not isinstance(value, str) or len(value) > 180:
        return False
    parts = value.split(".")
    if len(parts) != 4 or parts[0] != _PREFIX:
        return False
    try:
        code_branch = int(parts[1])
        window = int(parts[2])
    except (ValueError, OverflowError):
        return False
    if code_branch != int(branch_id):
        return False
    current = int(timestamp) // WINDOW_SECONDS
    if window not in (current, current - 1):
        return False
    return hmac.compare_digest(parts[3], _signature(branch_id, window))


def build_scan_url(code, base_url=None):
    base = (base_url or os.getenv("APP_BASE_URL", "")).strip().rstrip("/")
    if not base or not (base.startswith("https://") or base.startswith("http://")):
        raise RuntimeError("APP_BASE_URL moet naar het publieke adres van de app verwijzen.")
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}clock={quote(code, safe='')}"


def qr_svg(value):
    """Generate an SVG QR image without sending the token to an external service."""
    try:
        import qrcode
        import qrcode.image.svg
    except ImportError as exc:
        raise RuntimeError("De qrcode-package ontbreekt. Installeer de projectrequirements opnieuw.") from exc

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(value)
    qr.make(fit=True)
    image = qr.make_image(image_factory=qrcode.image.svg.SvgPathImage)
    output = io.BytesIO()
    image.save(output)
    return output.getvalue().decode("utf-8")
