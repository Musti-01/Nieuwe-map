from datetime import datetime
import streamlit as st
from workforce.i18n import tr

KINDS = {'sick': 'Ziekte', 'leave': 'Verlof'}
STATUSES = {'pending': 'In afwachting', 'approved': 'Goedgekeurd', 'rejected': 'Geweigerd', 'cancelled': 'Geannuleerd'}


def show_absences(api, token, branch_id, admin, member, tz, run):
    st.subheader(tr('Afwezigheden'))
    st.caption(tr('Ziekte wordt direct gemeld. Verlof wacht op goedkeuring van een beheerder. Vermeld geen medische details.'))
    if member:
        with st.form(f'absence_request_{branch_id}'):
            kind = st.selectbox(tr('Soort afwezigheid'), ['sick', 'leave'], format_func=lambda k: tr(KINDS[k]))
            start = st.date_input(tr('Eerste afwezigheidsdag'), value=datetime.now(tz).date())
            end = st.date_input(tr('Laatste afwezigheidsdag'), value=datetime.now(tz).date())
            if st.form_submit_button(tr('Afwezigheid indienen')):
                if run(lambda: api.request_absence(token, branch_id, kind, start, end), 'Afwezigheid opgeslagen.'):
                    st.rerun()
    absences = run(lambda: api.absences(token, branch_id, team=admin))
    if absences is None:
        return
    if not absences:
        st.info(tr('Er zijn geen afwezigheden.'))
    for absence in absences:
        with st.container(border=True):
            st.text(f"{absence['name']} · {tr(KINDS[absence['kind']])} · {absence['start']:%d-%m-%Y} – {absence['end']:%d-%m-%Y} · {tr(STATUSES[absence['status']])}")
            if admin and absence['kind'] == 'leave' and absence['status'] == 'pending':
                for action, label in [('approve', 'Goedkeuren'), ('reject', 'Weigeren')]:
                    if st.button(tr(label), key=f"absence_{action}_{absence['id']}"):
                        if run(lambda: api.review_absence(token, branch_id, absence['id'], action), 'Afwezigheid bijgewerkt.'):
                            st.rerun()
            if absence['status'] in ('pending', 'approved'):
                # The service also checks ownership, status and current permissions.
                if admin or absence['status'] == 'pending':
                    if st.button(tr('Annuleren'), key=f"absence_cancel_{absence['id']}"):
                        if run(lambda: api.review_absence(token, branch_id, absence['id'], 'cancel'), 'Afwezigheid bijgewerkt.'):
                            st.rerun()
