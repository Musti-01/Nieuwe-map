"""Task-based starting page for branch managers."""
import streamlit as st
from workforce.i18n import tr


def show_manager_home(api, token, branch_id, page_key, run):
    st.subheader(tr('Jouw vestiging beheren'))
    st.write(tr('Wat wil je doen? Kies hieronder een actie.'))

    def navigate(target):
        st.session_state[page_key] = target

    actions = [
        ('Medewerkers toevoegen', 'Nodig een nieuwe medewerker uit voor deze vestiging.'),
        ('Planning', 'Plan diensten en bekijk wie wanneer werkt.'),
        ('Medewerkers & rechten', 'Bekijk je team en beheer de toegang en rollen.'),
        ('Werkuren', 'Bekijk gewerkte uren per medewerker en periode.'),
        ('Shiften controleren', 'Controleer, corrigeer en keur geregistreerde uren goed.'),
        ('Meldingen', 'Bekijk vergeten uitklokacties en openstaande controles.'),
    ]
    for offset in range(0, len(actions), 2):
        for col, (target, explanation) in zip(st.columns(2), actions[offset:offset+2]):
            with col.container(border=True):
                st.button(tr(target), key=f'manager_open_{target}', on_click=navigate,
                          args=(target,), use_container_width=True, type='primary')
                st.caption(tr(explanation))
    entries = run(lambda: api.entries(token, branch_id, team=True))
    members = run(lambda: api.members(token, branch_id))
    if entries is None or members is None:
        return
    a, b, c = st.columns(3)
    a.metric(tr('Actieve teamleden'), sum(m['active'] and m['role'] != 'revoked' for m in members))
    b.metric(tr('Nu aan het werk'), sum(e['end'] is None for e in entries))
    c.metric(tr('Shiften te controleren'), sum(e['end'] is not None and e['review_status'] != 'approved' for e in entries))
