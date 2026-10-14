import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from workforce.db import make_engine, sessions
from workforce.service import Service, Denied, now
from workforce.reports import period_bounds, hours

st.set_page_config(page_title="ShiftFlow · Personeel & tijd", page_icon="⏱", layout="wide")
st.markdown("""<style>
.block-container {max-width:1200px;padding-top:2rem;}
h1,h2,h3 {color:#006491;} [data-testid=stMetric] {background:#F1F5FA;padding:1rem;border-radius:12px;border-top:3px solid #E31837;}
[data-testid=stSidebar] {border-right:1px solid #DDE5EF;}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def backend():
    engine = make_engine()
    if os.getenv('AUTO_MIGRATE') == '1':
        from workforce.hosting import migrate
        migrate(engine)
    return Service(sessions(engine))

try:
    api = backend()
except (RuntimeError, SQLAlchemyError):
    st.error("Database nog niet geconfigureerd. Stel DATABASE_URL in en voer de migraties uit; zie README.")
    st.stop()

def run(action, success=None):
    try:
        value = action()
        if success:
            st.session_state['notice'] = success
        return value
    except (ValueError, Denied) as exc:
        st.error(str(exc))
    except SQLAlchemyError:
        st.error("Database niet beschikbaar. Neem contact op met de beheerder.")
    return None

st.title("ShiftFlow")
st.caption("Personeel & tijd · Eén platform voor al jouw vestigingen")
if 'notice' in st.session_state:
    st.success(st.session_state.pop('notice'))
token = st.session_state.get('token')
if token:
    try:
        me = api.identity(token)
    except Denied:
        st.session_state.clear()
        st.warning("Sessie verlopen. Log opnieuw in.")
        token = None
    except SQLAlchemyError:
        st.error("Database niet beschikbaar.")
        st.stop()

if not token:
    login_tab, signup_tab = st.tabs(["Inloggen", "Registreren"])
    with login_tab:
        st.subheader("Welkom terug")
        with st.form("login"):
            email = st.text_input("E-mailadres")
            password = st.text_input("Wachtwoord", type="password")
            if st.form_submit_button("Inloggen", type="primary"):
                result = run(lambda: api.login(email, password))
                if result:
                    st.session_state['token'] = result
                    st.rerun()
    with signup_tab:
        st.subheader("Start met jouw team")
        is_owner = st.checkbox("Ik registreer een organisatie met een eerste vestiging", value=True)
        with st.form("signup", clear_on_submit=True):
            name = st.text_input("Volledige naam")
            email = st.text_input("E-mailadres", key="signup_email")
            password = st.text_input("Wachtwoord (minimaal 12 tekens)", type="password")
            confirm = st.text_input("Herhaal wachtwoord", type="password")
            if is_owner:
                address = st.text_input("Vestigingsadres (straat, nummer, postcode en plaats)")
                phone = st.text_input("Contacttelefoon")
                org = st.text_input("Organisatienaam / franchisenemer")
                chain = st.text_input("Restaurantketen")
                branch = st.text_input("Naam eerste vestiging")
            st.caption("Medewerkers registreren een persoonlijk account. Een bevoegde beheerder koppelt hen daarna aan een vestiging.")
            if st.form_submit_button("Account aanmaken", type="primary"):
                if password != confirm:
                    st.error("De wachtwoorden komen niet overeen.")
                else:
                    result = run(lambda: api.register(email, name, password, org if is_owner else None, chain if is_owner else None, branch if is_owner else None, address if is_owner else None, phone if is_owner else None), "Account aangemaakt. Je kunt nu inloggen; organisaties en vestigingen wachten eerst op goedkeuring.")
                    if result:
                        st.rerun()
    st.stop()

with st.sidebar:
    st.subheader(me['name'])
    st.caption("Platformeigenaar" if me['platform_owner'] else "Platformbeheerder" if me['platform_admin'] else me['email'])
    if st.button("Uitloggen", use_container_width=True):
        run(lambda: api.logout(token))
        st.session_state.clear()
        st.rerun()


if me['platform_admin']:
    with st.sidebar:
        workspace = st.radio("Werkruimte", ["Platformdashboard", "Vestigingen"])
    if workspace == "Platformdashboard":
        from workforce.ui_platform import show_platform
        show_platform(api, token, me, run)
        st.stop()

branches = run(lambda: api.branches(token))
if branches is None:
    st.stop()
organizations = run(lambda: api.organizations(token)) or []
if organizations:
    with st.sidebar.expander("Vestiging toevoegen"):
        with st.form("branch"):
            org_id = st.selectbox("Organisatie", [o['id'] for o in organizations], format_func=lambda i: next(o['name'] for o in organizations if o['id'] == i))
            name = st.text_input("Vestigingsnaam")
            address = st.text_input("Vestigingsadres")
            if st.form_submit_button("Toevoegen"):
                if run(lambda: api.add_branch(token, org_id, name, address), "Vestigingsaanvraag ingediend; wacht op platformgoedkeuring."):
                    st.rerun()
if not branches:
    st.info("Je account is klaar. Vraag jouw beheerder om je via jouw e-mailadres aan een vestiging te koppelen.")
    st.stop()

with st.sidebar:
    branch_id = st.selectbox("Actieve vestiging", [b['id'] for b in branches], format_func=lambda i: next(f"{b['organization']} · {b['name']}" for b in branches if b['id'] == i))
b = next(b for b in branches if b['id'] == branch_id)
st.subheader(b['name'])
labels = {"pending": "In afwachting", "approved": "Goedgekeurd", "rejected": "Geweigerd", "blocked": "Geblokkeerd"}
if b['status'] != 'approved' or b['organization_status'] != 'approved':
    st.warning(f"Organisatie: {labels[b['organization_status']]} · Vestiging: {labels[b['status']]}")
    st.info("Operationele toegang en rolbeheer worden beschikbaar zodra de platformbeheerder zowel de organisatie als de vestiging goedkeurt. Bij blokkering vervalt de toegang direct.")
    st.stop()
st.caption(f"{b['organization']} · {'Organisatie-eigenaar' if b['owner'] else 'Vestigingsadmin' if b['admin'] else 'Medewerker'}")
tabs = st.tabs(["In- en uitklokken", "Mijn shiften"] + (["Dashboard", "Shiften controleren", "Team & rechten", "Auditlog"] if b['admin'] else []))
zone = os.getenv('APP_TIMEZONE', 'Europe/Brussels')
try:
    tz = ZoneInfo(zone)
except Exception:
    st.error("APP_TIMEZONE is ongeldig.")
    st.stop()

with tabs[0]:
    entries = run(lambda: api.entries(token, branch_id))
    if entries is None:
        st.stop()
    active = next((e for e in entries if not e['end']), None)
    st.write("🟢 Je bent ingeklokt" if active else "Je bent momenteel uitgeklokt")
    if b['member']:
        a, c = st.columns(2)
        with a:
            if st.button("Inklokken", type="primary", disabled=active is not None, use_container_width=True):
                if run(lambda: api.clock_in(token, branch_id), "Je bent ingeklokt."):
                    st.rerun()
        with c:
            if st.button("Uitklokken", disabled=active is None, use_container_width=True):
                if run(lambda: api.clock_out(token, branch_id), "Je bent uitgeklokt."):
                    st.rerun()
    st.caption("Een actieve sessie in een andere vestiging moet je daar eerst afsluiten.")
    st.caption("Onderstaande uren zijn geregistreerd en kunnen nog op controle wachten. Definitief goedgekeurde uren staan bij Mijn shiften.")
    today = datetime.now(tz).date()
    columns = st.columns(3)
    for col, period in zip(columns, ["Dag", "Week", "Maand"]):
        begin, end = period_bounds(today, period, zone)
        total = sum(r['Uren'] for r in hours(entries, begin, end, now()))
        col.metric(f"Deze {period.lower()}", f"{total:.2f} uur")

with tabs[1]:
    from workforce.shift_view import shift_rows
    st.subheader("Mijn shiften")
    st.write("Jouw geregistreerde shiften in deze vestiging, met begin, einde, status en gewerkte uren.")
    st.caption("Dit zijn geklokte diensten. Toekomstige shiften inplannen is nog niet beschikbaar.")
    period = st.selectbox("Toon shiften per", ["Dag", "Week", "Maand"], index=2)
    day = st.date_input("Kies een datum in de gewenste periode", value=datetime.now(tz).date())
    begin, end = period_bounds(day, period, zone)
    snapshot = now()
    rows = shift_rows(entries, begin, end, tz, snapshot)
    total = sum(r['Uren'] for r in hours(entries, begin, end, snapshot))
    a, c, d = st.columns(3)
    approved = sum(r['Uren'] for r in hours([e for e in entries if e['review_status'] == 'approved'], begin, end, snapshot))
    a.metric("Shiften in deze periode", len(rows))
    c.metric("Goedgekeurde uren", f"{approved:.2f} uur")
    d.metric("Geregistreerde uren (alle statussen)", f"{total:.2f} uur")
    st.caption("Duur in de tabel geldt voor de volledige shift; het urentotaal hierboven telt alleen het deel binnen de gekozen periode. Lopende shiften tellen mee tot het laatste verversen.")
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info("Je hebt nog geen shiften in deze periode. Gebruik In- en uitklokken om een shift te starten.")
    if entries:
        with st.expander("Mijn correcties en goedkeuringen"):
            selected = st.selectbox("Mijn shift bekijken", [e['id'] for e in entries], format_func=lambda i: next(e['start'].astimezone(tz).strftime('%d-%m-%Y %H:%M') for e in entries if e['id'] == i))
            history = run(lambda: api.shift_history(token, branch_id, selected))
            if history:
                st.dataframe(history, hide_index=True, use_container_width=True)
            else:
                st.caption("Nog geen correcties of goedkeuringen voor deze shift.")
    if st.button("Shiften verversen"):
        st.rerun()

if b['admin']:
    with tabs[2]:
        team = run(lambda: api.entries(token, branch_id, team=True))
        if team is None:
            st.stop()
        st.subheader("Nu aan het werk")
        active = [e for e in team if not e['end']]
        st.metric("Ingeklokte medewerkers", len(active))
        if active:
            st.dataframe([{"Medewerker": e['name'], "Sinds": e['start'].astimezone(tz)} for e in active], hide_index=True, use_container_width=True)
        period = st.selectbox("Periode", ["Dag", "Week", "Maand"])
        day = st.date_input("Datum", value=datetime.now(tz).date())
        begin, end = period_bounds(day, period, zone)
        snapshot = now()
        for label, selected in [("Goedgekeurde uren", [e for e in team if e['review_status'] == 'approved']), ("Wacht op controle", [e for e in team if e['end'] is not None and e['review_status'] != 'approved']), ("Lopende uren (voorlopig)", [e for e in team if e['end'] is None])]:
            totals = hours(selected, begin, end, snapshot)
            st.metric(label, f"{sum(r['Uren'] for r in totals):.2f} uur")
            if totals:
                st.dataframe(totals, hide_index=True, use_container_width=True)
        st.caption("Alleen goedgekeurde uren zijn gecontroleerd. Ongecontroleerde en lopende uren staan apart. Periodes worden berekend in de ingestelde tijdzone.")
    with tabs[3]:
        from workforce.ui_review import show_reviews
        show_reviews(api, token, branch_id, team, me, tz, run)
    with tabs[4]:
        st.subheader("Medewerkers & bevoegdheden")
        members = run(lambda: api.members(token, branch_id))
        st.dataframe(members or [], hide_index=True, use_container_width=True)
        with st.form(f"find_{branch_id}"):
            email = st.text_input("Selecteer een bestaande gebruiker via exact e-mailadres")
            find = st.form_submit_button("Gebruiker zoeken")
        if find:
            result = run(lambda: api.lookup_user(token, branch_id, email))
            st.session_state[f"target_{branch_id}"] = result
            if not result:
                st.info("Geen gebruiker gevonden. Laat de medewerker eerst een persoonlijk account registreren.")
        target = st.session_state.get(f"target_{branch_id}")
        if target:
            st.write(f"Geselecteerd: {target['name']} ({target['email']})")
            with st.form(f"role_{branch_id}"):
                roles = {"Medewerker": "employee", "Toegang intrekken": None}
                if b['owner']:
                    roles["Vestigingsadmin"] = "admin"
                role = st.selectbox("Bevoegdheid", list(roles))
                if st.form_submit_button("Bevoegdheid opslaan"):
                    try:
                        api.set_role(token, branch_id, target['id'], roles[role])
                        st.session_state['notice'] = "Bevoegdheid bijgewerkt."
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))
                    except SQLAlchemyError:
                        st.error("Database niet beschikbaar.")
        st.caption("Alleen organisatie-eigenaars en platformbeheerders kunnen vestigingsadmins aanwijzen of hun rechten intrekken.")
    with tabs[5]:
        st.dataframe(run(lambda: api.audit(token, branch_id)) or [], hide_index=True, use_container_width=True)
