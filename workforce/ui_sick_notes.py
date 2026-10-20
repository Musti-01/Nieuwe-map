import streamlit as st
from workforce.i18n import tr
from workforce.sick_notes import MAX_SIZE, INVALID_FILE


def show_sick_notes(api, token, branch_id, admin, member, tz, run):
    st.subheader(tr('Ziektebriefjes'))
    st.caption(tr('Een ziektebrief is zichtbaar voor jou en de bevoegde beheerders van deze vestiging.'))
    if member:
        with st.form(f'sick_note_upload_{branch_id}', clear_on_submit=True):
            upload = st.file_uploader(tr('Ziektebrief uploaden (PDF, PNG of JPG, maximaal 5 MB)'),
                                      type=['pdf', 'png', 'jpg', 'jpeg'])
            if st.form_submit_button(tr('Ziektebrief indienen')):
                if upload is None or upload.size > MAX_SIZE:
                    st.error(tr(INVALID_FILE))
                elif run(lambda: api.upload_sick_note(token, branch_id, upload.name, upload.getvalue())):
                    st.success(tr('Ziektebrief opgeslagen.'))
    notes = run(lambda: api.sick_notes(token, branch_id, team=admin))
    if notes is None:
        return
    if not notes:
        st.info(tr('Er zijn nog geen ziektebriefjes ingediend.'))
    for note in notes:
        # No document contents are included in listings or cached in session_state.
        with st.expander(f"{note['name']} · {note['uploaded_at'].astimezone(tz):%d-%m-%Y %H:%M} · {note['filename']}"):
            if st.button(tr('Bestand ophalen'), key=f"sick_note_fetch_{branch_id}_{note['id']}"):
                document = run(lambda: api.download_sick_note(token, branch_id, note['id']))
                if document:
                    st.download_button(tr('Ziektebrief downloaden'), data=document['content'],
                                       file_name=document['filename'], mime=document['media_type'],
                                       key=f"sick_note_download_{branch_id}_{note['id']}", on_click='ignore')
