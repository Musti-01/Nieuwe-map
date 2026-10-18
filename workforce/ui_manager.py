"""Task-based starting page for branch managers."""
import streamlit as st
from datetime import datetime, time, timedelta
from workforce import service
from workforce.clock_policy import clock_in_allowed
from workforce.i18n import tr
from workforce.ui_navigation import open_shift_review


def show_manager_home(api, token, branch_id, page_key, run, tz):
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

    plans = run(lambda: api.plans(token, branch_id, team=True))
    if plans is None:
        return
    snapshot = service.now()
    day = snapshot.astimezone(tz).date()
    begin = datetime.combine(day, time.min, tzinfo=tz)
    end = datetime.combine(day + timedelta(days=1), time.min, tzinfo=tz)
    today = [p for p in plans if p['status'] == 'scheduled' and p['start'] < end and p['end'] > begin]
    st.subheader(tr('Vandaag in je vestiging'))
    st.caption(tr('Planning voor {v0}. Ook nachtdiensten die vandaag doorlopen staan hieronder.', v0=day.strftime('%d-%m-%Y')))
    rows = []
    for p in today:
        status = ('Afgesloten' if p['actual_end'] else 'Aan het werk' if p['entry_id'] is not None
                  else 'Niet geregistreerd' if p['end'] <= snapshot else 'Nog niet ingeklokt' if p['start'] <= snapshot
                  else 'Kan nu inklokken' if clock_in_allowed(p['start'], p['end'], snapshot, tz) else 'Start later')
        rows.append({tr('Medewerker'): p['name'], tr('Gepland begin'): p['start'].astimezone(tz).strftime('%d-%m %H:%M'),
                     tr('Gepland einde'): p['end'].astimezone(tz).strftime('%d-%m %H:%M'), tr('Status'): tr(status)})
    if rows:
        st.dataframe(rows, hide_index=True, use_container_width=True)
    else:
        st.info(tr('Vandaag is nog niemand ingepland. Open Planning om een shift toe te voegen.'))
    active = [e for e in entries if e['end'] is None]
    if active:
        st.subheader(tr('Nu aan het werk'))
        st.dataframe([{tr('Medewerker'): e['name'], tr('Sinds'): e['start'].astimezone(tz).strftime('%d-%m-%Y %H:%M')} for e in active], hide_index=True, use_container_width=True)
    alerts = run(lambda: api.alerts(token, branch_id, team=True)) or []
    if alerts:
        st.subheader(tr('Dit vraagt aandacht'))
        for alert in alerts[:3]:
            st.write(tr('{v0}: {v1}', v0=alert['medewerker'], v1=tr(alert['melding'])))
            st.button(tr('Shift bekijken en controleren'), key=f"home_review_{alert['shift']}",
                      on_click=open_shift_review, args=(branch_id, alert['shift']))
        if len(alerts) > 3:
            st.caption(tr('Bekijk alle meldingen via Meldingen.'))
    if st.button(tr('Overzicht verversen')):
        st.rerun()
