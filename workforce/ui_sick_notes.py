from datetime import datetime
import streamlit as st
from workforce.i18n import tr
from workforce.sick_notes import MAX_SIZE, INVALID_FILE, retention_days


def show_sick_notes(api, token, branch_id, admin, member, tz, run):
    st.subheader(tr('Ziektebriefjes'))
    st.caption(tr('Alleen platformbeheerders kunnen ziektebriefjes downloaden en verwijderen.'))
    st.caption(tr('Bewaring: {v0} dagen na de laatste ziektedag of upload, afhankelijk van wat later is.', v0=retention_days()))
    if member:
        absences = run(lambda: api.absences(token, branch_id)) or []
        sick = {a['id']: a for a in absences if a['kind'] == 'sick' and a['status'] == 'approved'}
        with st.form(f'sick_note_upload_{branch_id}', clear_on_submit=True):
            absence_id = st.selectbox(tr('Koppel aan ziekmelding'), [None] + list(sick),
                format_func=lambda i: tr('Nieuwe ziekmelding') if i is None else f"{sick[i]['start']:%d-%m-%Y} – {sick[i]['end']:%d-%m-%Y}")
            start = st.date_input(tr('Eerste ziektedag (nieuwe melding)'), value=datetime.now(tz).date())
            end = st.date_input(tr('Laatste ziektedag (nieuwe melding)'), value=datetime.now(tz).date())
            upload = st.file_uploader(tr('Ziektebrief uploaden (PDF, PNG of JPG, maximaal 5 MB)'), type=['pdf', 'png', 'jpg', 'jpeg'])
            if st.form_submit_button(tr('Ziektebrief indienen')):
                if upload is None or upload.size > MAX_SIZE:
                    st.error(tr(INVALID_FILE))
                elif run(lambda: api.upload_sick_note(token, branch_id, upload.name, upload.getvalue(), start, end, absence_id)):
                    st.success(tr('Ziektebrief opgeslagen.'))
    notes = run(lambda: api.sick_notes(token, branch_id, team=admin))
    if notes is None:
        return
    if not notes:
        st.info(tr('Er zijn nog geen ziektebriefjes ingediend.'))
    for note in notes:
        with st.expander(f"{note['name']} · {note['uploaded_at'].astimezone(tz):%d-%m-%Y %H:%M} · {note['filename']}"):
            st.caption(tr('Wordt verwijderd na {v0}.', v0=note['expires_at'].astimezone(tz).strftime('%d-%m-%Y')))
            if not admin:
                continue
            if st.button(tr('Bestand ophalen'), key=f"sick_note_fetch_{branch_id}_{note['id']}"):
                document = run(lambda: api.download_sick_note(token, branch_id, note['id']))
                if document:
                    st.download_button(tr('Ziektebrief downloaden'), data=document['content'],
                        file_name=document['filename'], mime=document['media_type'],
                        key=f"sick_note_download_{branch_id}_{note['id']}", on_click='ignore')
            confirmed = st.checkbox(tr('Deze ziektebrief definitief verwijderen'), key=f"sick_note_delete_confirm_{note['id']}")
            if st.button(tr('Ziektebrief verwijderen'), key=f"sick_note_delete_{note['id']}", disabled=not confirmed):
                if run(lambda: api.delete_sick_note(token, branch_id, note['id']), 'Ziektebrief verwijderd.'):
                    st.rerun()
