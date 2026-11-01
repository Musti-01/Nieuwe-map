import os
import hashlib
import time
from urllib.parse import quote

import streamlit as st
from workforce.i18n import tr
from workforce.qr_clock import WINDOW_SECONDS, build_employee_code, qr_svg
from workforce.service import Denied


def show_employee_qr(api, token, employee_id, branch_id, tz):
    """Show rotating employee QR and refresh into a clock-in confirmation."""
    marker = f"qr_active_seen_{branch_id}"

    @st.fragment(run_every=3)
    def live():
        try:
            entries = api.entries(token, branch_id)
        except (ValueError, Denied) as exc:
            st.error(tr(str(exc)))
            return
        active = next((e for e in entries if e["end"] is None), None)
        if active:
            st.success(tr(
                "Ingeklokt om {v0}.",
                v0=active["start"].astimezone(tz).strftime("%H:%M:%S"),
            ))
            st.caption(tr("Je kunt hieronder uitklokken wanneer je klaar bent."))
            if not st.session_state.get(marker):
                st.session_state[marker] = True
                st.session_state["notice"] = tr(
                    "Inklokken bevestigd om {v0}.",
                    v0=active["start"].astimezone(tz).strftime("%H:%M:%S"),
                )
                st.rerun()
            return

        st.session_state.pop(marker, None)
        try:
            code = build_employee_code(employee_id, branch_id)
            svg = qr_svg(code)
        except RuntimeError as exc:
            st.error(tr(str(exc)))
            return
        st.image(svg, width=330, alt=tr("Persoonlijke QR-code"))
        remaining = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        st.metric(tr("Nieuwe QR over"), tr("{v0} sec", v0=remaining))
        st.caption(tr(
            "Toon deze persoonlijke QR alleen aan de geautoriseerde winkelscanner. "
            "De scanner controleert daarna opnieuw je vestiging, planning en afwezigheden."
        ))

    live()


def show_scanner_management(api, token, branch_id, run):
    st.subheader(tr("Winkelscanners"))
    st.write(tr(
        "Registreer alleen vaste scanners of tablets die in de vestiging worden gebruikt. "
        "Elke scanner krijgt een eigen geheime toegang die je later kunt intrekken."
    ))

    with st.form(f"create_scanner_{branch_id}", clear_on_submit=True):
        name = st.text_input(tr("Scannernaam"), placeholder=tr("Bijvoorbeeld: Tablet kassa 1"))
        if st.form_submit_button(tr("Scanner registreren"), type="primary"):
            created = run(lambda: api.create_scanner(token, branch_id, name))
            if created:
                st.session_state[f"new_scanner_{branch_id}"] = created
                st.rerun()

    created = st.session_state.pop(f"new_scanner_{branch_id}", None)
    if created:
        base = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
        st.success(tr("Scanner geregistreerd. Deze koppeling wordt slechts één keer getoond."))
        if base:
            link = f"{base}?scanner={quote(created['token'], safe='')}"
            st.code(link, language=None)
            st.caption(tr(
                "Open deze link alleen op het vaste winkeltoestel. Wie deze link bezit, heeft scannerrechten "
                "totdat je de scanner intrekt."
            ))
        else:
            st.warning(tr("APP_BASE_URL ontbreekt; stel eerst het publieke app-adres in om een koppellink te maken."))

    devices = run(lambda: api.scanners(token, branch_id))
    if devices is None:
        return
    if devices:
        st.dataframe([
            {
                tr("Scanner"): d["name"],
                tr("Status"): tr("Actief") if d["active"] else tr("Ingetrokken"),
                tr("Aangemaakt"): d["created_at"],
                tr("Laatst gezien"): d["last_seen_at"],
            }
            for d in devices
        ], hide_index=True, use_container_width=True)
        active = [d for d in devices if d["active"]]
        if active:
            chosen = st.selectbox(
                tr("Scanner intrekken"),
                [d["id"] for d in active],
                format_func=lambda i: next(d["name"] for d in active if d["id"] == i),
            )
            if st.button(tr("Scannerrechten intrekken")):
                if run(lambda: api.revoke_scanner(token, branch_id, chosen), "Scanner ingetrokken."):
                    st.rerun()
    else:
        st.info(tr("Nog geen winkelscanner geregistreerd."))


def _decode_camera_qr(photo):
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise RuntimeError("Camera-scanning is niet beschikbaar; installeer de projectrequirements opnieuw.") from exc
    raw = np.frombuffer(photo.getvalue(), dtype=np.uint8)
    image = cv2.imdecode(raw, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("De camerafoto kon niet worden gelezen.")
    value, points, _ = cv2.QRCodeDetector().detectAndDecode(image)
    value = (value or "").strip()
    if not value:
        raise ValueError("Geen geldige QR-code gevonden. Houd de QR volledig en scherp in beeld.")
    return value


def show_scanner_station(api, scanner_token, tz):
    try:
        info = api.scanner_info(scanner_token)
    except (ValueError, Denied) as exc:
        st.error(tr(str(exc)))
        st.stop()

    st.title(tr("ShiftFlow winkelscanner"))
    st.subheader(info["branch_name"])
    st.caption(tr("{v0} · {v1}", v0=info["organization"], v1=info["scanner_name"]))
    st.write(tr(
        "Scan de persoonlijke QR van de medewerker met een vaste QR-scanner of met de camera van deze tablet."
    ))

    def process_scan(qr_value):
        try:
            result = api.scanner_clock_in(scanner_token, qr_value)
            st.session_state["scanner_last_success"] = result
            return True
        except (ValueError, Denied) as exc:
            st.error(tr(str(exc)))
        return False

    hardware_tab, camera_tab = st.tabs([tr("USB/Bluetooth scanner"), tr("Tablet-camera")])
    with hardware_tab:
        st.caption(tr(
            "Een vaste QR-scanner werkt als toetsenbord: scan de code en druk zo nodig op Scan verwerken."
        ))
        with st.form("scanner_form", clear_on_submit=True):
            qr_value = st.text_input(
                tr("QR-scan"),
                type="password",
                autocomplete="off",
                placeholder=tr("Scan nu de QR-code"),
            )
            submitted = st.form_submit_button(tr("Scan verwerken"), type="primary", use_container_width=True)
        if submitted:
            process_scan(qr_value)

    with camera_tab:
        st.caption(tr("Maak met de tablet-camera een scherpe foto van de volledige QR-code."))
        photo = st.camera_input(tr("Scan QR met camera"), key="scanner_camera")
        if photo is not None:
            photo_hash = hashlib.sha256(photo.getvalue()).hexdigest()
            if st.session_state.get("scanner_camera_processed") != photo_hash:
                try:
                    decoded = _decode_camera_qr(photo)
                    st.session_state["scanner_camera_processed"] = photo_hash
                    process_scan(decoded)
                except (ValueError, RuntimeError) as exc:
                    st.session_state["scanner_camera_processed"] = photo_hash
                    st.error(tr(str(exc)))

    result = st.session_state.pop("scanner_last_success", None)
    if result:
        local = result["clocked_in_at"].astimezone(tz)
        st.success(tr("{v0} is succesvol ingeklokt.", v0=result["name"]))
        st.metric(tr("Geregistreerde inkloktijd"), local.strftime("%H:%M:%S"))
        st.caption(tr(
            "Shift: {v0} – {v1}",
            v0=result["plan_start"].astimezone(tz).strftime("%H:%M"),
            v1=result["plan_end"].astimezone(tz).strftime("%H:%M"),
        ))

    st.info(tr(
        "Een doorgestuurde live QR blijft een risico zolang hij nog geldig is. "
        "Daarom accepteert ShiftFlow alleen scans van deze geautoriseerde winkelscanner, "
        "verbruikt elke QR maar één keer en bewaart de scanner in het auditspoor."
    ))

