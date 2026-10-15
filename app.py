from workforce.i18n import tr, translated_formatter, translated_table, set_language, LANGUAGES
import os
from datetime import datetime
from zoneinfo import ZoneInfo
import streamlit as st
from sqlalchemy.exc import SQLAlchemyError
from workforce.db import make_engine, sessions
from workforce.service import Service, Denied, now
from workforce.reports import period_bounds, hours
from workforce.ui_accounts import account_links, password_settings, invitations, clear_signin

set_language(st.session_state.get("language", "nl"))

st.set_page_config(page_title=tr("ShiftFlow · Personeel & tijd"), page_icon="⏱", layout="wide")
st.markdown("""<style>
.block-container {max-width:1200px;padding-top:2rem;}
h1,h2,h3 {color:#006491;} [data-testid=stMetric] {background:#F1F5FA;padding:1rem;border-radius:12px;border-top:3px solid #E31837;}
[data-testid=stSidebar] {border-right:1px solid #DDE5EF;}
</style>""", unsafe_allow_html=True)

@st.cache_resource
def backend_engine(schema_revision="0006"):
    engine = make_engine()
    if os.getenv('AUTO_MIGRATE') == '1':
        from workforce.hosting import migrate
        migrate(engine)
    return engine

try:
    # Cache only the engine: service code must refresh with application updates.
    api = Service(sessions(backend_engine()))
except (RuntimeError, SQLAlchemyError):
    st.error(tr('Database nog niet geconfigureerd. Stel DATABASE_URL in en voer de migraties uit; zie README.'))
    st.stop()

def run(action, success=None):
    try:
        value = action()
        if success:
            st.session_state['notice'] = success
        return value
    except (ValueError, Denied) as exc:
        st.error(tr(str(exc)))
    except SQLAlchemyError:
        st.error(tr('Database niet beschikbaar. Neem contact op met de beheerder.'))
    return None

token = st.session_state.get('token')
if token:
    try:
        me = api.identity(token)
    except Denied:
        clear_signin()
        st.warning(tr('Sessie verlopen. Log opnieuw in.'))
        token = None
    except SQLAlchemyError:
        st.error(tr('Database niet beschikbaar.'))
        st.stop()

if token and st.session_state.get('_language_account') != me['id']:
    st.session_state['language'] = me['language']
    st.session_state['_language_account'] = me['id']
if 'language' not in st.session_state:
    st.session_state['language'] = 'nl'

def language_changed():
    set_language(st.session_state['language'])
    if st.session_state.get('token'):
        try:
            api.set_language(st.session_state['token'], st.session_state['language'])
        except (ValueError, SQLAlchemyError):
            st.session_state['language_save_error'] = True

with st.columns([3, 1])[1]:
    st.selectbox('Taal / Language', list(LANGUAGES), format_func=lambda code: LANGUAGES[code], key='language', on_change=language_changed)
set_language(st.session_state['language'])
st.set_page_config(page_title=tr('ShiftFlow · Personeel & tijd'))
if st.session_state.pop('language_save_error', False):
    st.warning(tr('Je taalkeuze kon niet worden opgeslagen. Probeer opnieuw.'))

st.title(tr('ShiftFlow'))
st.caption(tr('Personeel & tijd · Eén platform voor al jouw vestigingen'))
if 'notice' in st.session_state:
    st.success(tr(st.session_state.pop('notice')))

account_links(api, token, run)

if not token:
    login_tab, signup_tab = st.tabs([tr('Inloggen'), tr('Registreren')])
    with login_tab:
        st.subheader(tr('Welkom terug'))
        with st.form("login"):
            email = st.text_input(tr('E-mailadres'))
            password = st.text_input(tr('Wachtwoord'), type="password")
            if st.form_submit_button(tr('Inloggen'), type="primary"):
                result = run(lambda: api.login(email, password))
                if result:
                    st.session_state['token'] = result
                    st.rerun()
        with st.expander(tr('Wachtwoord vergeten?')):
            st.caption(tr('Een herstellink wordt alleen per e-mail verzonden wanneer de platformeigenaar e-mailverzending heeft ingesteld.'))
            with st.form("request_reset"):
                reset_email=st.text_input(tr('E-mailadres voor wachtwoordherstel'))
                if st.form_submit_button(tr('Herstellink aanvragen')):
                    if run(lambda: api.request_password_reset(reset_email)):
                        st.success(tr('Als dit een actief account is, staat een herstellink klaar voor verzending. Controleer je e-mail.'))
    with signup_tab:
        st.subheader(tr('Start met jouw team'))
        is_owner = st.checkbox(tr('Ik registreer een organisatie met een eerste vestiging'), value=True)
        with st.form("signup", clear_on_submit=True):
            name = st.text_input(tr('Volledige naam'))
            email = st.text_input(tr('E-mailadres'), key="signup_email")
            password = st.text_input(tr('Wachtwoord (minimaal 12 tekens)'), type="password")
            confirm = st.text_input(tr('Herhaal wachtwoord'), type="password")
            if is_owner:
                address = st.text_input(tr('Vestigingsadres (straat, nummer, postcode en plaats)'))
                phone = st.text_input(tr('Contacttelefoon'))
                org = st.text_input(tr('Organisatienaam / franchisenemer'))
                chain = st.text_input(tr('Restaurantketen'))
                branch = st.text_input(tr('Naam eerste vestiging'))
            st.caption(tr('Medewerkers registreren een persoonlijk account. Een bevoegde beheerder koppelt hen daarna aan een vestiging.'))
            if st.form_submit_button(tr('Account aanmaken'), type="primary"):
                if password != confirm:
                    st.error(tr('De wachtwoorden komen niet overeen.'))
                else:
                    result = run(lambda: api.register(email, name, password, org if is_owner else None, chain if is_owner else None, branch if is_owner else None, address if is_owner else None, phone if is_owner else None, language=st.session_state["language"]), "Account aangemaakt. Je kunt nu inloggen; organisaties en vestigingen wachten eerst op goedkeuring.")
                    if result:
                        st.rerun()
    st.stop()

with st.sidebar:
    st.subheader(me['name'])
    st.caption((tr('Platformeigenaar') if me['platform_owner'] else (tr('Platformbeheerder') if me['platform_admin'] else me['email'])))
    password_settings(api, token, run)
    if st.button(tr('Uitloggen'), use_container_width=True):
        run(lambda: api.logout(token))
        clear_signin()
        st.rerun()


if me['platform_admin']:
    with st.sidebar:
        workspace = st.radio(tr('Werkruimte'), ["Platformdashboard", "Vestigingen"], format_func=tr)
    if workspace == "Platformdashboard":
        from workforce.ui_platform import show_platform
        show_platform(api, token, me, run)
        st.stop()

branches = run(lambda: api.branches(token))
if branches is None:
    st.stop()
organizations = run(lambda: api.organizations(token)) or []
if organizations:
    with st.sidebar.expander(tr('Vestiging toevoegen')):
        with st.form("branch"):
            org_id = st.selectbox(tr('Organisatie'), [o['id'] for o in organizations], format_func=translated_formatter(lambda i: next((o['name'] for o in organizations if o['id'] == i))))
            name = st.text_input(tr('Vestigingsnaam'))
            address = st.text_input(tr('Vestigingsadres'))
            if st.form_submit_button(tr('Toevoegen')):
                if run(lambda: api.add_branch(token, org_id, name, address), "Vestigingsaanvraag ingediend; wacht op platformgoedkeuring."):
                    st.rerun()
if not branches:
    st.info(tr('Je account is klaar. Vraag jouw beheerder om je via jouw e-mailadres aan een vestiging te koppelen.'))
    st.stop()

with st.sidebar:
    branch_id = st.selectbox(tr('Actieve vestiging'), [b['id'] for b in branches], format_func=translated_formatter(lambda i: next((tr('{v0} · {v1}', v0=b['organization'], v1=b['name']) for b in branches if b['id'] == i))))
b = next(b for b in branches if b['id'] == branch_id)
st.subheader(b['name'])
labels = {"pending": "In afwachting", "approved": "Goedgekeurd", "rejected": "Geweigerd", "blocked": "Geblokkeerd"}
if b['status'] != 'approved' or b['organization_status'] != 'approved':
    st.warning(tr('Organisatie: {v0} · Vestiging: {v1}', v0=tr(labels[b['organization_status']]), v1=tr(labels[b['status']])))
    st.info(tr('Operationele toegang en rolbeheer worden beschikbaar zodra de platformbeheerder zowel de organisatie als de vestiging goedkeurt. Bij blokkering vervalt de toegang direct.'))
    st.stop()
st.caption(tr('{v0} · {v1}', v0=b['organization'], v1=tr('Organisatie-eigenaar' if b['owner'] else 'Vestigingsadmin' if b['admin'] else 'Medewerker')))
tabs = st.tabs((([tr('In- en uitklokken'), tr('Mijn shiften')] + ([tr('Dashboard'), tr('Shiften controleren'), tr('Team & rechten'), tr('Auditlog')] if b['admin'] else [])) + [tr('Planning'), tr('Meldingen')]))
zone = os.getenv('APP_TIMEZONE', 'Europe/Brussels')
try:
    tz = ZoneInfo(zone)
except Exception:
    st.error(tr('APP_TIMEZONE is ongeldig.'))
    st.stop()

with tabs[0]:
    entries = run(lambda: api.entries(token, branch_id))
    if entries is None:
        st.stop()
    my_plans = run(lambda: api.plans(token, branch_id)) or []
    choices = [p for p in my_plans if p['status']=='scheduled' and p['entry_id'] is None]
    plan_id = st.selectbox(tr('Inklokken voor'), [None]+[p['id'] for p in choices], format_func=translated_formatter(lambda i: tr('Zonder geplande shift') if i is None else next((tr('{v0:%d-%m %H:%M} – {v1:%H:%M}', v0=p['start'].astimezone(tz), v1=p['end'].astimezone(tz)) for p in choices if p['id'] == i))))
    active = next((e for e in entries if not e['end']), None)
    st.write((tr('🟢 Je bent ingeklokt') if active else tr('Je bent momenteel uitgeklokt')))
    if b['member']:
        a, c = st.columns(2)
        with a:
            if st.button(tr('Inklokken'), type="primary", disabled=active is not None, use_container_width=True):
                if run(lambda: api.clock_in(token, branch_id, plan_id), "Je bent ingeklokt."):
                    st.rerun()
        with c:
            if st.button(tr('Uitklokken'), disabled=active is None, use_container_width=True):
                if run(lambda: api.clock_out(token, branch_id), "Je bent uitgeklokt."):
                    st.rerun()
    st.caption(tr('Een actieve sessie in een andere vestiging moet je daar eerst afsluiten.'))
    st.caption(tr('Onderstaande uren zijn geregistreerd en kunnen nog op controle wachten. Definitief goedgekeurde uren staan bij Mijn shiften.'))
    today = datetime.now(tz).date()
    columns = st.columns(3)
    for col, period in zip(columns, ["Dag", "Week", "Maand"]):
        begin, end = period_bounds(today, period, zone)
        total = sum(r['Uren'] for r in hours(entries, begin, end, now()))
        col.metric(tr({'Dag':'Vandaag','Week':'Deze week','Maand':'Deze maand'}[period]), tr('{v0:.2f} uur', v0=total))

with tabs[1]:
    from workforce.shift_view import shift_rows
    st.subheader(tr('Mijn shiften'))
    st.write(tr('Jouw geregistreerde shiften in deze vestiging, met begin, einde, status en gewerkte uren.'))
    st.caption(tr('Dit zijn geklokte diensten. Toekomstige diensten vind je bij Planning.'))
    period = st.selectbox(tr('Toon shiften per'), ["Dag", "Week", "Maand"], index=2, format_func=tr)
    day = st.date_input(tr('Kies een datum in de gewenste periode'), value=datetime.now(tz).date())
    begin, end = period_bounds(day, period, zone)
    snapshot = now()
    rows = shift_rows(entries, begin, end, tz, snapshot)
    total = sum(r['Uren'] for r in hours(entries, begin, end, snapshot))
    a, c, d = st.columns(3)
    approved = sum(r['Uren'] for r in hours([e for e in entries if e['review_status'] == 'approved'], begin, end, snapshot))
    a.metric(tr('Shiften in deze periode'), tr(len(rows)))
    c.metric(tr('Goedgekeurde uren'), tr('{v0:.2f} uur', v0=approved))
    d.metric(tr('Geregistreerde uren (alle statussen)'), tr('{v0:.2f} uur', v0=total))
    st.caption(tr('Duur in de tabel geldt voor de volledige shift; het urentotaal hierboven telt alleen het deel binnen de gekozen periode. Lopende shiften tellen mee tot het laatste verversen.'))
    if rows:
        st.dataframe(translated_table(rows), hide_index=True, use_container_width=True)
    else:
        st.info(tr('Je hebt nog geen shiften in deze periode. Gebruik In- en uitklokken om een shift te starten.'))
    if entries:
        with st.expander(tr('Mijn correcties en goedkeuringen')):
            selected = st.selectbox(tr('Mijn shift bekijken'), [e['id'] for e in entries], format_func=translated_formatter(lambda i: next((e['start'].astimezone(tz).strftime('%d-%m-%Y %H:%M') for e in entries if e['id'] == i))))
            history = run(lambda: api.shift_history(token, branch_id, selected))
            if history:
                st.dataframe(translated_table(history), hide_index=True, use_container_width=True)
            else:
                st.caption(tr('Nog geen correcties of goedkeuringen voor deze shift.'))
    if st.button(tr('Shiften verversen')):
        st.rerun()

if b['admin']:
    with tabs[2]:
        team = run(lambda: api.entries(token, branch_id, team=True))
        if team is None:
            st.stop()
        st.subheader(tr('Nu aan het werk'))
        active = [e for e in team if not e['end']]
        st.metric(tr('Ingeklokte medewerkers'), tr(len(active)))
        if active:
            st.dataframe(translated_table([{'Medewerker': e['name'], 'Sinds': e['start'].astimezone(tz)} for e in active]), hide_index=True, use_container_width=True)
        period = st.selectbox(tr('Periode'), ["Dag", "Week", "Maand"], format_func=tr)
        day = st.date_input(tr('Datum'), value=datetime.now(tz).date())
        begin, end = period_bounds(day, period, zone)
        snapshot = now()
        for label, selected in [("Goedgekeurde uren", [e for e in team if e['review_status'] == 'approved']), ("Wacht op controle", [e for e in team if e['end'] is not None and e['review_status'] != 'approved']), ("Lopende uren (voorlopig)", [e for e in team if e['end'] is None])]:
            totals = hours(selected, begin, end, snapshot)
            st.metric(tr(label), tr('{v0:.2f} uur', v0=sum((r['Uren'] for r in totals))))
            if totals:
                st.dataframe(translated_table(totals), hide_index=True, use_container_width=True)
        st.caption(tr('Alleen goedgekeurde uren zijn gecontroleerd. Ongecontroleerde en lopende uren staan apart. Periodes worden berekend in de ingestelde tijdzone.'))
    with tabs[3]:
        from workforce.ui_review import show_reviews
        show_reviews(api, token, branch_id, team, me, tz, run)
    with tabs[4]:
        st.subheader(tr('Medewerkers & bevoegdheden'))
        invitations(api, token, branch_id, run)
        members = run(lambda: api.members(token, branch_id))
        st.dataframe(translated_table(members or []), hide_index=True, use_container_width=True)
        with st.form(f"find_{branch_id}"):
            email = st.text_input(tr('Selecteer een bestaande gebruiker via exact e-mailadres'))
            find = st.form_submit_button(tr('Gebruiker zoeken'))
        if find:
            result = run(lambda: api.lookup_user(token, branch_id, email))
            st.session_state[f"target_{branch_id}"] = result
            if not result:
                st.info(tr('Geen gebruiker gevonden. Laat de medewerker eerst een persoonlijk account registreren.'))
        target = st.session_state.get(f"target_{branch_id}")
        if target:
            st.write(tr('Geselecteerd: {v0} ({v1})', v0=target['name'], v1=target['email']))
            with st.form(f"role_{branch_id}"):
                roles = {"Medewerker": "employee", "Toegang intrekken": None}
                if b['owner']:
                    roles["Vestigingsadmin"] = "admin"
                role = st.selectbox(tr('Bevoegdheid'), list(roles), format_func=tr)
                if st.form_submit_button(tr('Bevoegdheid opslaan')):
                    try:
                        api.set_role(token, branch_id, target['id'], roles[role])
                        st.session_state['notice'] = "Bevoegdheid bijgewerkt."
                        st.rerun()
                    except ValueError as exc:
                        st.error(tr(str(exc)))
                    except SQLAlchemyError:
                        st.error(tr('Database niet beschikbaar.'))
        st.caption(tr('Alleen organisatie-eigenaars en platformbeheerders kunnen vestigingsadmins aanwijzen of hun rechten intrekken.'))
    with tabs[5]:
        st.dataframe(translated_table(run(lambda: api.audit(token, branch_id)) or []), hide_index=True, use_container_width=True)

with tabs[-2]:
    from workforce.ui_planning import show_planning
    show_planning(api, token, branch_id, b['admin'], tz, zone, run)
with tabs[-1]:
    from workforce.ui_planning import show_alerts
    show_alerts(api, token, branch_id, b['admin'], run)
