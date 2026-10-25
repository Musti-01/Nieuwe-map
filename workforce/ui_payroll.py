from datetime import datetime
from decimal import Decimal
import streamlit as st
from workforce.i18n import tr
from workforce.payroll import euros

KINDS = {'hourly': 'Uurloon', 'monthly': 'Vast maandloon'}
BASES = {'gross': 'Bruto', 'net': 'Netto afgesproken'}


def show_payroll(api, token, branch_id, tz, run):
    st.subheader(tr('Lonen'))
    st.write(tr('Bereken het maandloon per medewerker op basis van de loonafspraak en goedgekeurde uren.'))
    day = st.date_input(tr('Loonmaand'), value=datetime.now(tz).date(), key=f'payroll_month_{branch_id}')
    month = day.replace(day=1)
    st.caption(tr('Overzicht voor {v0}.', v0=month.strftime('%m-%Y')))
    rows = run(lambda: api.monthly_payroll(token, branch_id, month))
    if rows is None:
        return
    if not rows:
        st.info(tr('Koppel eerst een actieve medewerker via Medewerkers & rechten.'))
        return
    gross = sum((r['amount'] for r in rows if r['amount'] is not None and r['rate']['basis'] == 'gross'), Decimal(0))
    net = sum((r['amount'] for r in rows if r['amount'] is not None and r['rate']['basis'] == 'net'), Decimal(0))
    a, b, c = st.columns(3)
    a.metric(tr('Goedgekeurde uren'), f"{sum((r['approved_hours'] for r in rows), Decimal(0)):.2f}")
    b.metric(tr('Bruto basisloon'), euros(gross))
    c.metric(tr('Netto volgens afspraak'), euros(net))
    table = []
    for row in rows:
        rate = row['rate']
        status = ('Loon nog niet ingesteld' if rate is None else 'Controleer contract' if row['needs_contract_check']
                  else 'Uren wachten op controle' if row['pending_hours'] or row['active_hours'] else 'Berekend')
        table.append({tr('Medewerker'): row['name'], tr('Loonafspraak'): tr(KINDS[rate['kind']]) if rate else '—',
                      tr('Basis'): tr(BASES[rate['basis']]) if rate else '—',
                      tr('Tarief'): euros(rate['amount']) if rate else '—',
                      tr('Goedgekeurde uren'): f"{row['approved_hours']:.2f}",
                      tr('Wacht op controle'): f"{row['pending_hours']:.2f}",
                      tr('Lopende uren'): f"{row['active_hours']:.2f}",
                      tr('Te betalen volgens afspraak'): euros(row['amount']) if row['amount'] is not None else '—',
                      tr('Status'): tr(status)})
    st.dataframe(table, hide_index=True, use_container_width=True)
    if any(r['rate'] is None for r in rows):
        st.warning(tr('Voor sommige medewerkers ontbreekt een loonafspraak. Hun loon is niet opgenomen in de totalen.'))
    if any(r['pending_hours'] or r['active_hours'] for r in rows):
        st.warning(tr('Lopende en niet-goedgekeurde uren tellen nog niet mee. Controleer deze uren om het loonoverzicht aan te vullen.'))
    if any(r['needs_contract_check'] for r in rows):
        st.warning(tr('Bij voormalige medewerkers met maandloon is contractcontrole nodig. Hun bedrag is niet in de totalen opgenomen.'))
    st.caption(tr('Uurloon: goedgekeurde uren × tarief. Vast maandloon: het afgesproken maandbedrag, zonder automatische verrekening van ziekte, verlof of een onvolledige maand.'))
    st.info(tr('Dit is een loonberekening volgens afspraak. Belastingen, bijdragen, toeslagen en bankoverschrijvingen worden niet automatisch uitgevoerd. Bruto bedragen zijn geen netto uitbetaling.'))

    eligible = {r['user_id']: r for r in rows if r['active']}
    if not eligible:
        return
    with st.expander(tr('Loon per medewerker instellen'), expanded=any(r['rate'] is None for r in rows)):
        uid = st.selectbox(tr('Medewerker voor looninstelling'), list(eligible),
                          format_func=lambda i: eligible[i]['name'], key=f'salary_employee_{branch_id}')
        row = eligible[uid]
        rate = row['rate']
        with st.form(f'salary_rate_{branch_id}_{uid}_{month.isoformat()}', clear_on_submit=True):
            kind = st.selectbox(tr('Loonafspraak'), list(KINDS), index=1 if rate and rate['kind'] == 'monthly' else 0, format_func=lambda k: tr(KINDS[k]))
            basis = st.selectbox(tr('Bedrag is'), list(BASES), index=1 if rate and rate['basis'] == 'net' else 0, format_func=lambda k: tr(BASES[k]))
            amount = st.number_input(tr('Afgesproken bedrag in euro'), min_value=0.01, max_value=1000000.0,
                                     value=float(rate['amount']) if rate else None, step=0.01, format='%.2f')
            st.caption(tr('De afspraak gaat in op de eerste dag van de geselecteerde loonmaand en blijft gelden tot een nieuwe afspraak.'))
            if st.form_submit_button(tr('Loonafspraak opslaan'), type='primary'):
                if run(lambda: api.set_salary_rate(token, branch_id, uid, kind, amount, basis, month), 'Loonafspraak opgeslagen.'):
                    st.rerun()
