import time
import streamlit as st

from workforce.i18n import tr
from workforce.qr_store import WINDOW_SECONDS, build_scan_url, build_store_code, qr_svg


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
