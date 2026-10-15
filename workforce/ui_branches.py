"""Simple platform branch removal with one explicit confirmation."""
import streamlit as st
from workforce.i18n import tr


def branch_management(api, token, run):
    st.write(tr('Verwijder een vestiging met één bevestiging. De toegang stopt direct; de historiek blijft bewaard.'))
    archived = st.toggle(tr('Verwijderde vestigingen tonen'))
    search = st.text_input(tr('Zoek vestiging of organisatie')).strip().casefold()
    branches = run(lambda: api.platform_branches(token, archived=archived))
    if branches is None:
        return
    visible = [b for b in branches if search in (b['name'] + ' ' + b['organization']).casefold()]
    if not visible:
        st.info(tr('Geen vestigingen gevonden.'))
    for b in visible:
        with st.container(border=True):
            st.subheader(b['name'])
            st.text(b['organization'])
            st.text(b['address'])
            if archived:
                if st.button(tr('Herstellen'), key=f"restore_branch_{b['id']}"):
                    if run(lambda: api.archive_branch(token, b['id'], restore=True), 'Vestiging hersteld. Eerdere rechten en goedkeuringsstatus gelden opnieuw.'):
                        st.rerun()
            elif st.session_state.get('remove_branch') == b['id']:
                st.warning(tr('Deze vestiging verwijderen? Actieve shiften worden afgesloten. Medewerkers verliezen direct toegang.'))
                if st.button(tr('Ja, vestiging verwijderen'), key=f"confirm_branch_{b['id']}", type='primary'):
                    if run(lambda: api.archive_branch(token, b['id']), 'Vestiging verwijderd. De toegang is stopgezet.'):
                        st.session_state.pop('remove_branch', None)
                        st.rerun()
                if st.button(tr('Annuleren'), key=f"cancel_branch_{b['id']}"):
                    st.session_state.pop('remove_branch', None)
                    st.rerun()
            elif st.button(tr('Verwijderen'), key=f"remove_branch_{b['id']}"):
                st.session_state['remove_branch'] = b['id']
                st.rerun()
