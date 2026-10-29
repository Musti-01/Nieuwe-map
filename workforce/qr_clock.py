"""Rotating employee QR credentials and authenticated in-store scan challenge.

The QR code is a short-lived HMAC proof of employee identity, NOT permission to clock in.
A trusted in-store scanner must be provisioned separately before using the server side.
"""
import base64
import hashlib
import hmac
import os
import time


WINDOW_SECONDS = 15


def _key():
    secret = os.getenv("SHIFTFLOW_QR_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("SHIFTFLOW_QR_SECRET moet minimaal 32 tekens bevatten.")
    return secret.encode("utf-8")


def _signature(user_id, branch_id, window):
    message = f"shiftflow:v1:{int(user_id)}:{int(branch_id)}:{int(window)}".encode()
    raw = hmac.new(_key(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(raw[:20]).decode().rstrip("=")


def build_code(user_id, branch_id, timestamp=None):
    timestamp = time.time() if timestamp is None else timestamp
    window = int(timestamp) // WINDOW_SECONDS
    return f"sf1.{int(user_id)}.{int(branch_id)}.{window}.{_signature(user_id, branch_id, window)}"


def verify_code(value, branch_id, timestamp=None):
    """Returns employee user ID or None. Allows current and previous window."""
    timestamp = time.time() if timestamp is None else timestamp
    if not isinstance(value, str) or len(value) > 180:
        return None
    parts = value.split(".")
    if len(parts) != 5 or parts[0] != "sf1":
        return None
    try:
        user_id = int(parts[1])
        code_branch = int(parts[2])
        window = int(parts[3])
    except (ValueError, OverflowError):
        return None
    if user_id <= 0 or code_branch != int(branch_id):
        return None
    if window not in (int(timestamp) // WINDOW_SECONDS, int(timestamp) // WINDOW_SECONDS - 1):
        return None
    if not hmac.compare_digest(parts[4], _signature(user_id, branch_id, window)):
        return None
    return user_id


def scanner_authorized(scanner_key):
    configured = os.getenv("SHIFTFLOW_SCANNER_KEY", "")
    if len(configured) < 32 or not isinstance(scanner_key, str):
        return False
    return hmac.compare_digest(scanner_key, configured)
