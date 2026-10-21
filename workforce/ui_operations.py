from datetime import datetime, timedelta, timezone
import streamlit as st
from workforce.i18n import tr


def show_operations(api, token, run):
    status = run(lambda: api.system_status(token))
    if status is None:
        return
    st.subheader(tr('Systeemstatus'))
    if status['mail_configured']:
        st.info(tr('E-maildienst ingesteld. Controleer de afleveringen en fouten hieronder.'))
    else:
        st.warning(tr('E-maildienst nog niet ingesteld. Wachtwoordherstel is nog niet actief.'))
    if status['last_backup'] is None:
        st.warning(tr('Er is nog geen geslaagde back-up geregistreerd.'))
    else:
        st.text(tr('Laatste back-up: {v0}', v0=status['last_backup'].isoformat()))
        if status['last_backup'] < datetime.now(timezone.utc)-timedelta(hours=26):
            st.warning(tr('De laatste back-up is ouder dan 26 uur. Controleer de geplande taak.'))
    st.caption(tr('Dit overzicht bewijst geen herstelbaarheid. Test herstel regelmatig op een aparte database.'))
    if status['events']:
        st.dataframe([{tr('Tijd'): e['time'], tr('Categorie'): e['category'], tr('Foutcode'): e['code']} for e in status['events']], hide_index=True, use_container_width=True)
    if st.button(tr('Status verversen')):
        st.rerun()
