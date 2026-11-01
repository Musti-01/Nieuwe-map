import time
import streamlit as st

from workforce.i18n import tr
from workforce.qr_clock import WINDOW_SECONDS, build_store_code, build_store_url, qr_svg


def show_store_qr(branch_id, branch_name):
    st.subheader(tr("QR-inklokken"))
    st.write(tr(
        "Toon deze QR-code in de vestiging. Medewerkers scannen hem met de camera van hun eigen gsm om in te klokken."
    ))
    st.caption(tr(
        "De QR-code verandert automatisch elke 15 seconden. Na het scannen controleert ShiftFlow het account, de vestiging, de geplande shift en afwezigheden."
    ))

    @st.fragment(run_every=3)
    def live_store_qr():
        try:
            code = build_store_code(branch_id)
            url = build_store_url(code)
            svg = qr_svg(url)
        except RuntimeError as exc:
            st.error(tr(str(exc)))
            return

        st.markdown(svg.decode("utf-8"), unsafe_allow_html=True)
        remaining = WINDOW_SECONDS - (int(time.time()) % WINDOW_SECONDS)
        st.metric(tr("Nieuwe QR over"), tr("{v0} sec", v0=remaining))
        st.caption(tr("Vestiging: {v0}", v0=branch_name))

    live_store_qr()

    st.info(tr(
        "Medewerkers kunnen niet rechtstreeks vanuit hun account inklokken. Ze moeten een actuele QR-code van deze vestiging scannen. "
        "Een doorgestuurde live QR blijft tijdens de korte geldigheid een risico; daarom verloopt hij snel en kan dezelfde medewerker dezelfde QR maar één keer gebruiken."
    ))
