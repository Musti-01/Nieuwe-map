"""Readable audit history; stored evidence and technical codes stay unchanged."""
import streamlit as st
from workforce.i18n import tr

ACTIONS = {
    'sick_note.uploaded': 'Ziektebrief ingediend',
    'sick_note.downloaded': 'Ziektebrief opgehaald',
    'approval.approve': 'Vestiging goedgekeurd',
    'approval.reject': 'Vestiging geweigerd',
    'approval.block': 'Vestiging geblokkeerd',
    'approval.reactivate': 'Vestiging opnieuw geactiveerd',
    'branch.created': 'Vestiging aangevraagd',
    'branch.archived': 'Vestiging verwijderd',
    'branch.restored': 'Vestiging hersteld',
    'membership.changed': 'Rechten gewijzigd',
    'clock.in': 'Ingeklokt',
    'clock.out': 'Uitgeklokt',
    'clock.closed_by_block': 'Shift afgesloten door blokkering',
    'clock.closed_by_archive': 'Shift afgesloten door verwijdering van vestiging',
    'clock.closed_by_deactivation': 'Shift afgesloten door deactivering van account',
    'shift.correct': 'Werkuren gecorrigeerd',
    'shift.approve': 'Werkuren goedgekeurd',
    'account.invited': 'Medewerker uitgenodigd',
    'invitation.accepted': 'Uitnodiging geaccepteerd',
    'plan.saved': 'Planning opgeslagen',
    'plan.cancelled': 'Geplande shift geannuleerd',
}
STATUSES = {'pending': 'In afwachting', 'approved': 'Goedgekeurd', 'blocked': 'Geblokkeerd', 'rejected': 'Geweigerd'}
ROLES = {'employee': 'Medewerker', 'admin': 'Vestigingsadmin', 'revoked': 'Toegang ingetrokken'}


def audit_rows(events, tz):
    rows = []
    for e in events:
        details = []
        if e.get('role') in ROLES:
            details.append(tr(ROLES[e['role']]))
        if e.get('previous_status') in STATUSES and e.get('status') in STATUSES:
            details.append(tr(STATUSES[e['previous_status']]) + ' → ' + tr(STATUSES[e['status']]))
        if e['actie'] == 'shift.correct' and e.get('new_start'):
            def interval(start, end):
                return start.astimezone(tz).strftime('%d-%m-%Y %H:%M') + ' – ' + (end.astimezone(tz).strftime('%d-%m-%Y %H:%M') if end else tr('Nog bezig'))
            details.append(tr('Van {v0} naar {v1}', v0=interval(e['old_start'], e['old_end']), v1=interval(e['new_start'], e['new_end'])))
        if e.get('reason'):
            details.append(e['reason'])
        rows.append({tr('Datum en tijd'): e['tijd'].astimezone(tz).strftime('%d-%m-%Y %H:%M:%S'),
                     tr('Uitgevoerd door'): e['actor_name'], tr('Gebeurtenis'): tr(ACTIONS.get(e['actie'], 'Overige wijziging')),
                     tr('Betreft'): e.get('subject') or '—', tr('Toelichting'): ' · '.join(details) or '—'})
    return rows


def show_audit(api, token, branch_id, tz, run):
    st.subheader(tr('Wijzigingsgeschiedenis'))
    st.write(tr('Hier zie je wie iets heeft gewijzigd en wanneer. Dit overzicht wordt automatisch bijgehouden.'))
    st.caption(tr('De laatste 100 gebeurtenissen, met de meest recente bovenaan. Tijdzone: {v0}.', v0=str(tz)))
    events = run(lambda: api.audit(token, branch_id))
    if events is None:
        return
    if not events:
        st.info(tr('Er zijn nog geen wijzigingen geregistreerd.'))
        return
    st.dataframe(audit_rows(events, tz), hide_index=True, use_container_width=True)
    with st.expander(tr('Technische gegevens (voor ondersteuning)')):
        st.caption(tr('De oorspronkelijke registratie blijft bewaard voor controle en ondersteuning.'))
        st.dataframe([{'tijd': e['tijd'], 'actor': e['actor'], 'actie': e['actie'], 'detail': e['detail']} for e in events], hide_index=True, use_container_width=True)
