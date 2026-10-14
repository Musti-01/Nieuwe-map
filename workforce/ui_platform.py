import streamlit as st
from sqlalchemy.exc import SQLAlchemyError


def show_platform(api, token, me, run):
    labels = {"pending": "In afwachting", "approved": "Goedgekeurd", "rejected": "Geweigerd", "blocked": "Geblokkeerd"}
    pages = ["Overzicht", "Aanvragen", "Besluitgeschiedenis"]
    if me['platform_owner']:
        pages.append("Platformbeheerders")
    if st.session_state.get('platform_page') not in pages:
        st.session_state['platform_page'] = 'Overzicht'
    with st.sidebar:
        page = st.radio("Platformonderdeel", pages, key="platform_page")
    st.subheader("Platformbeheer · " + page)
    applications = run(lambda: api.applications(token))
    if applications is None:
        st.stop()
    if page == "Overzicht":
        st.write("Beheer hier de toegang van organisaties en vestigingen tot ShiftFlow.")
        a, b, c = st.columns(3)
        a.metric("Aanvragen die op jouw besluit wachten", sum(r['status'] == 'pending' for r in applications))
        b.metric("Organisaties", sum(r['kind'] == 'organization' for r in applications))
        c.metric("Vestigingen", sum(r['kind'] == 'branch' for r in applications))
        st.markdown("### Wat kun je hier doen?")
        def navigate(target):
            st.session_state['platform_page'] = target
        st.markdown("**Aanvragen beoordelen** — bekijk bedrijfs- en contactgegevens. Keur eerst een organisatie en daarna iedere vestiging goed, of weiger met een reden.")
        st.button("Naar aanvragen en blokkeringen", on_click=navigate, args=("Aanvragen",), type="primary")
        st.markdown("**Toegang blokkeren of herstellen** — kies bij Aanvragen een goedgekeurde of geblokkeerde organisatie/vestiging. Blokkeren sluit actieve shiften af; heractiveren bewaart de eerdere gegevens.")
        st.markdown("**Besluiten controleren** — bekijk wie een besluit nam, wanneer en met welke reden.")
        st.button("Bekijk besluitgeschiedenis", on_click=navigate, args=("Besluitgeschiedenis",))
        if me['platform_owner']:
            st.markdown("**Platformbeheerders machtigen** — geef een bestaand account platformrechten of trek die in. Alleen jij als platformeigenaar kunt dit doen.")
            st.button("Beheer platformbeheerders", on_click=navigate, args=("Platformbeheerders",))
        st.markdown("**Vestigingen, medewerkers en uren beheren** — kies links bij Werkruimte voor **Vestigingen**. Selecteer daar een vestiging voor het team, rollen, uren en auditlog.")
        st.info("Medewerkers beheren: in de vestiging bij Team & rechten. Accountverwijdering, volledige accountdeactivering en shiftplanning zijn nog niet beschikbaar.")
        st.caption("E-mails bij besluiten worden in een wachtrij gezet. Echte verzending vereist een geconfigureerde mailworker.")
    elif page == "Aanvragen":
        st.write("Keur eerst de organisatie goed, daarna haar vestigingen. Gebruik de statusfilter om ook blokkeringen te beheren.")
        status_filter = st.selectbox("Filter op status", ["Alle"] + list(labels.values()))
        visible = [r for r in applications if status_filter == "Alle" or labels[r['status']] == status_filter]
        st.dataframe([{"Type": "Organisatie" if r['kind'] == 'organization' else "Vestiging", "Bedrijf": r['bedrijf'], "Vestiging": r['vestiging'], "Status": labels[r['status']], "Adres": r['adres'], "Verantwoordelijke": r['verantwoordelijke'], "E-mailadres": r['email'], "Telefoon": r['telefoon'], "Aangevraagd": r['aangevraagd'], "Beoordeeld": r['beoordeeld']} for r in visible], hide_index=True, use_container_width=True)
        if visible:
            choices = {f"{r['kind']}:{r['id']}": r for r in visible}
            selected = st.selectbox("Aanvraag beoordelen", list(choices), format_func=lambda k: f"{choices[k]['bedrijf']} · {choices[k]['vestiging']} ({'Organisatie' if choices[k]['kind'] == 'organization' else 'Vestiging'}) · {labels[choices[k]['status']]}")
            item = choices[selected]
            st.write(f"Verantwoordelijke: {item['verantwoordelijke']}")
            st.write(f"Contact: {item['email']} · {item['telefoon']}")
            st.write(f"Adres: {item['adres'] or 'Niet opgegeven bij eerdere registratie'}")
            actions = {"pending": {"Goedkeuren": "approve", "Weigeren": "reject"}, "approved": {"Blokkeren": "block"}, "blocked": {"Opnieuw activeren": "reactivate"}, "rejected": {}}[item['status']]
            if actions:
                with st.form(f"decision_{selected}_{item['status']}"):
                    action = st.selectbox("Besluit", list(actions))
                    reason = st.text_area("Toelichting (verplicht bij weigeren of blokkeren)", max_chars=500)
                    if st.form_submit_button("Besluit bevestigen", type="primary"):
                        if run(lambda: api.decide(token, item['kind'], item['id'], actions[action], reason), "Besluit opgeslagen; bericht staat in de e-mailwachtrij."):
                            st.rerun()
        if not visible:
            st.info("Geen aanvragen met deze status.")
    elif page == "Besluitgeschiedenis":
        st.write("Alle besluiten met beoordelaar, tijdstip, statuswijziging en toelichting.")
        decisions = run(lambda: api.decisions(token))
        if decisions:
            st.dataframe(decisions, hide_index=True, use_container_width=True)
        else:
            st.info("Er zijn nog geen besluiten geregistreerd.")
    elif page == "Platformbeheerders" and me['platform_owner']:
        st.write("Zoek een bestaand persoonlijk account op exact e-mailadres. Machtigen geeft toegang tot alle platformaanvragen; intrekken beëindigt die rechten.")

        st.dataframe(run(lambda: api.platform_users(token)) or [], hide_index=True, use_container_width=True)
        with st.form("delegate"):
            email = st.text_input("E-mailadres bestaand account")
            enabled = st.checkbox("Machtiging als platformbeheerder actief", value=True)
            if st.form_submit_button("Machtiging opslaan"):
                try:
                    api.delegate_platform(token, email, enabled)
                    st.session_state['notice'] = "Platformmachtiging bijgewerkt."
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
                except SQLAlchemyError:
                    st.error("Database niet beschikbaar.")
