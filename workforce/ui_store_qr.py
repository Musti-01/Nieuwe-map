import hashlib
import time
from urllib.parse import parse_qs, urlsplit

import streamlit as st

from workforce.i18n import tr
from workforce.qr_store import WINDOW_SECONDS, PREFIX, build_scan_url, build_store_code, qr_svg, verify_store_code
from workforce.service import Denied


def show_store_qr(branch_id, branch_name):
    st.subheader(tr("QR-inklokken"))
    st.write(tr(
        "Toon deze QR-code op een scherm in de vestiging. Medewerkers scannen hem met hun eigen gsm om in te klokken."
    ))
    st.caption(tr(
        "De QR-code verandert automatisch elke 15 seconden. Uitklokken gebeurt later gewoon via de knop in het medewerkeraccount."
    ))

    @st.fragment(run_every=3)
    def live_qr():
        try:
            code = build_store_code(branch_id)
            url = build_scan_url(code)
            svg = qr_svg(url)
        except RuntimeError as exc:
            st.error(tr(str(exc)))
            return
        st.markdown(svg.decode("utf-8"), unsafe_allow_html=True)
        remaining = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        st.metric(tr("Nieuwe QR over"), tr("{v0} sec", v0=remaining))
        st.caption(tr("Vestiging: {v0}", v0=branch_name))

    live_qr()
    st.info(tr(
        "Een live QR kan tijdens de korte geldigheid worden doorgestuurd. Daarom is hij vestigingsgebonden, "
        "kort geldig en per medewerker maar één keer bruikbaar. Voor absolute fysieke aanwezigheidscontrole "
        "zou extra hardware of locatiecontrole nodig zijn."
    ))


def _decode_qr_photo(photo):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Camera-scanning is niet beschikbaar; installeer de projectrequirements opnieuw.") from exc
    raw = np.frombuffer(photo.getvalue(), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("De camerafoto kon niet worden gelezen.")
    value, _, _ = cv2.QRCodeDetector().detectAndDecode(image)
    value = (value or "").strip()
    if not value:
        raise ValueError("Geen geldige QR-code gevonden. Houd de QR volledig en scherp in beeld.")
    return value


def _store_code_from_scan(value):
    value = (value or "").strip()
    if value.startswith(PREFIX + "."):
        return value
    try:
        values = parse_qs(urlsplit(value).query).get("clock", [])
    except ValueError:
        values = []
    return values[0] if len(values) == 1 else ""


def show_employee_phone_scan(api, token, branch_id, tz):
    st.subheader(tr("QR scannen met je gsm"))
    st.caption(tr(
        "Open dit onderdeel op je gsm en scan de QR-code die in de vestiging wordt getoond. "
        "Na een geldige scan word je automatisch ingeklokt."
    ))
    photo = st.camera_input(tr("Scan de winkel-QR"), key=f"employee_store_qr_{branch_id}")
    if photo is None:
        return

    photo_hash = hashlib.sha256(photo.getvalue()).hexdigest()
    processed_key = f"employee_store_qr_processed_{branch_id}"
    if st.session_state.get(processed_key) == photo_hash:
        return

    st.session_state[processed_key] = photo_hash
    try:
        decoded = _decode_qr_photo(photo)
        code = _store_code_from_scan(decoded)
        data = verify_store_code(code)
        if not data:
            raise Denied("QR-code is ongeldig, vervalst of verlopen.")
        if data["branch_id"] != branch_id:
            raise Denied("Deze QR-code hoort bij een andere vestiging.")
        result = api.phone_qr_clock_in(token, code)
    except (ValueError, Denied, RuntimeError) as exc:
        st.error(tr(str(exc)))
        return

    local_time = result["clocked_in_at"].astimezone(tz).strftime("%H:%M:%S")
    st.session_state["notice"] = tr("Je bent ingeklokt om {v0}.", v0=local_time)
    st.rerun()
