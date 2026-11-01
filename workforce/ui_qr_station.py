import os
import time
import streamlit as st

from workforce.i18n import tr
from workforce.qr_station import (
    WINDOW_SECONDS,
    build_scan_url,
    build_station_code,
    qr_enabled,
    qr_svg,
)


def show_qr_station(branch_id, branch_name):
    st.subheader(tr("QR-inklokstation"))
    st.write(tr(
        "Toon dit scherm op een toestel in de vestiging. Medewerkers scannen de "
        "wisselende QR-code met hun telefoon om te kunnen inklokken."
    ))
    st.caption(tr(
        "Uitklokken blijft via de gewone knop. De QR verandert iedere 15 seconden "
        "en is alleen geldig voor deze vestiging."
    ))

    if not qr_enabled():
        st.warning(tr(
            "QR-inklokken staat nog uit. Zet SHIFTFLOW_QR_ENABLED=1 en configureer "
            "SHIFTFLOW_QR_SECRET veilig bij de host."
        ))
        return

    base_url = os.getenv("APP_BASE_URL", "").strip()
    if not base_url:
        st.error(tr(
            "APP_BASE_URL ontbreekt. Stel het publieke HTTPS-adres van ShiftFlow in "
            "voordat je het QR-station gebruikt."
        ))
        return

    @st.fragment(run_every=3)
    def live_qr():
        try:
            code = build_station_code(branch_id)
            scan_url = build_scan_url(code, base_url)
            svg = qr_svg(scan_url)
        except RuntimeError as exc:
            st.error(tr(str(exc)))
            return

        st.image(svg, width=360, alt=tr("QR-code om in te klokken"))
        remaining = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        st.metric(tr("Nieuwe QR over"), tr("{v0} sec", v0=remaining))
        st.caption(tr(
            "Vestiging: {v0}. Een oude of aangepaste QR-code wordt door de server geweigerd.",
            v0=branch_name,
        ))

    live_qr()

    st.info(tr(
        "Let op: een wisselende QR maakt inklokken van thuis veel moeilijker, maar een "
        "screenshot kan tijdens de korte geldigheid nog worden doorgestuurd. Voor sterke "
        "aanwezigheidscontrole is later een beheerde winkelscanner of extra locatiecontrole nodig."
    ))
