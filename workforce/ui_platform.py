from workforce.i18n import tr, translated_formatter, translated_table
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError


def show_platform(api, token, me, run):
    labels = {"pending": "In afwachting", "approved": "Goedgekeurd", "rejected": "Geweigerd", "blocked": "Geblokkeerd"}
    pages = ["Overzicht", "Aanvragen", "Besluitgeschiedenis", "Gebruikers", "Vestigingen beheren", "Systeemstatus"]
    if me['platform_owner']:
        pages.append("Platformbeheerders")
    if st.session_state.get('platform_page') not in pages:
        st.session_state['platform_page'] = 'Overzicht'
    with st.sidebar:
        page = st.radio(tr('Platformonderdeel'), pages, key="platform_page", format_func=tr)
    st.subheader((tr('Platformbeheer · ') + tr(page)))
    applications = run(lambda: api.applications(token))
    if applications is None:
        st.stop()
    if page == "Overzicht":
        st.write(tr('Beheer hier de toegang van organisaties en vestigingen tot ShiftFlow.'))
        a, b, c = st.columns(3)
        a.metric(tr('Aanvragen die op jouw besluit wachten'), tr(sum((r['status'] == 'pending' for r in applications))))
        b.metric(tr('Organisaties'), tr(sum((r['kind'] == 'organization' for r in applications))))
        c.metric(tr('Vestigingen'), tr(sum((r['kind'] == 'branch' for r in applications))))
        st.markdown(tr('### Wat kun je hier doen?'))
        def navigate(target):
            st.session_state['platform_page'] = target
        st.markdown(tr('**Aanvragen beoordelen** — bekijk bedrijfs- en contactgegevens. Keur eerst een organisatie en daarna iedere vestiging goed, of weiger met een reden.'))
        st.button(tr('Naar aanvragen en blokkeringen'), on_click=navigate, args=("Aanvragen",), type="primary")
        st.markdown(tr('**Toegang blokkeren of herstellen** — kies bij Aanvragen een goedgekeurde of geblokkeerde organisatie/vestiging. Blokkeren sluit actieve shiften af; heractiveren bewaart de eerdere gegevens.'))
        st.markdown(tr('**Besluiten controleren** — bekijk wie een besluit nam, wanneer en met welke reden.'))
        st.button(tr('Bekijk besluitgeschiedenis'), on_click=navigate, args=("Besluitgeschiedenis",))
        if me['platform_owner']:
            st.markdown(tr('**Platformbeheerders machtigen** — geef een bestaand account platformrechten of trek die in. Alleen jij als platformeigenaar kunt dit doen.'))
            st.button(tr('Beheer platformbeheerders'), on_click=navigate, args=("Platformbeheerders",))
        st.markdown(tr('**Vestigingen, medewerkers en uren beheren** — kies links bij Werkruimte voor **Vestigingen**. Selecteer daar een vestiging voor het team, rollen, uren en auditlog. Bij **Shiften controleren** kun je tijden met een reden corrigeren en uren goedkeuren; je eigen shifts moeten door een andere beheerder worden gecontroleerd.'))
        st.button(tr('Vestigingen beheren'), on_click=navigate, args=('Vestigingen beheren',))
        st.markdown(tr('**Accounts beheren** — bekijk gebruikers en deactiveer of heractiveer accounts. Historische gegevens blijven bewaard.'))
        st.button(tr('Beheer gebruikersaccounts'), on_click=navigate, args=("Gebruikers",))
        st.info(tr('Open een vestiging voor het beheeroverzicht: Medewerkers toevoegen voor uitnodigingen, Medewerkers & rechten voor rollen en Planning voor diensten.'))
        st.caption(tr('E-mails bij besluiten worden in een wachtrij gezet. Echte verzending vereist een geconfigureerde mailworker.'))
    elif page == "Aanvragen":
        st.write(tr('Keur eerst de organisatie goed, daarna haar vestigingen. Gebruik de statusfilter om ook blokkeringen te beheren.'))
        status_filter = st.selectbox(tr('Filter op status'), ["Alle"] + list(labels.values()), format_func=tr)
        visible = [r for r in applications if status_filter == "Alle" or labels[r['status']] == status_filter]
        st.dataframe(translated_table([{'Type': 'Organisatie' if r['kind'] == 'organization' else 'Vestiging', 'Bedrijf': r['bedrijf'], 'Vestiging': r['vestiging'], 'Status': labels[r['status']], 'Adres': r['adres'], 'Verantwoordelijke': r['verantwoordelijke'], 'E-mailadres': r['email'], 'Telefoon': r['telefoon'], 'Aangevraagd': r['aangevraagd'], 'Beoordeeld': r['beoordeeld']} for r in visible]), hide_index=True, use_container_width=True)
        if visible:
            choices = {f"{r['kind']}:{r['id']}": r for r in visible}
            selected = st.selectbox(tr('Aanvraag beoordelen'), list(choices), format_func=translated_formatter(lambda k: tr('{v0} · {v1} ({v2}) · {v3}', v0=choices[k]['bedrijf'], v1=choices[k]['vestiging'], v2=tr('Organisatie') if choices[k]['kind'] == 'organization' else tr('Vestiging'), v3=tr(labels[choices[k]['status']]))))
            item = choices[selected]
            st.write(tr('Verantwoordelijke: {v0}', v0=item['verantwoordelijke']))
            st.write(tr('Contact: {v0} · {v1}', v0=item['email'], v1=item['telefoon']))
            st.write(tr('Adres: {v0}', v0=item['adres'] or tr('Niet opgegeven bij eerdere registratie')))
            actions = {"pending": {"Goedkeuren": "approve", "Weigeren": "reject"}, "approved": {"Blokkeren": "block"}, "blocked": {"Opnieuw activeren": "reactivate"}, "rejected": {}}[item['status']]
            if actions:
                with st.form(f"decision_{selected}_{item['status']}"):
                    action = st.selectbox(tr('Besluit'), list(actions), format_func=tr)
                    reason = st.text_area(tr('Toelichting (verplicht bij weigeren of blokkeren)'), max_chars=500)
                    if st.form_submit_button(tr('Besluit bevestigen'), type="primary"):
                        if run(lambda: api.decide(token, item['kind'], item['id'], actions[action], reason), "Besluit opgeslagen; bericht staat in de e-mailwachtrij."):
                            st.rerun()
        if not visible:
            st.info(tr('Geen aanvragen met deze status.'))
    elif page == "Besluitgeschiedenis":
        st.write(tr('Alle besluiten met beoordelaar, tijdstip, statuswijziging en toelichting.'))
        decisions = run(lambda: api.decisions(token))
        if decisions:
            st.dataframe(translated_table(decisions), hide_index=True, use_container_width=True)
        else:
            st.info(tr('Er zijn nog geen besluiten geregistreerd.'))
    elif page == "Vestigingen beheren":
        from workforce.ui_branches import branch_management
        branch_management(api, token, run)
    elif page == "Systeemstatus":
        from workforce.ui_operations import show_operations
        show_operations(api, token, run)
    elif page == "Gebruikers":
        from workforce.ui_accounts import account_management
        account_management(api, token, run)
    elif page == "Platformbeheerders" and me['platform_owner']:
        st.write(tr('Zoek een bestaand persoonlijk account op exact e-mailadres. Machtigen geeft toegang tot alle platformaanvragen; intrekken beëindigt die rechten.'))

        st.dataframe(translated_table(run(lambda: api.platform_users(token)) or []), hide_index=True, use_container_width=True)
        with st.form("delegate"):
            email = st.text_input(tr('E-mailadres bestaand account'))
            enabled = st.checkbox(tr('Machtiging als platformbeheerder actief'), value=True)
            if st.form_submit_button(tr('Machtiging opslaan')):
                try:
                    api.delegate_platform(token, email, enabled)
                    st.session_state['notice'] = "Platformmachtiging bijgewerkt."
                    st.rerun()
                except ValueError as exc:
                    st.error(tr(str(exc)))
                except SQLAlchemyError as exc:
                    from workforce.operations import report_error
                    report_error(api.sessions, exc)
                    st.error(tr('Database niet beschikbaar.'))
