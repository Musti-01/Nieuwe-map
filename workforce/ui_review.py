from workforce.i18n import tr, translated_formatter, translated_table
from datetime import datetime
import streamlit as st


def show_reviews(api, token, branch_id, team, me, tz, run):
    st.subheader(tr('Shiften controleren'))
    st.write(tr('Controleer de werkelijk gewerkte tijden voordat je uren goedkeurt. Bij een vergeten uitklok kun je de shift hier afsluiten met de juiste eindtijd en een reden.'))
    status = st.selectbox(tr('Welke shiften controleren?'), ['Wacht op controle', 'Bezig', 'Goedgekeurd'], format_func=tr)
    eligible = [e for e in team if (e['end'] is None and status == 'Bezig') or (e['end'] is not None and ('Goedgekeurd' if e['review_status'] == 'approved' else 'Wacht op controle') == status)]
    if not eligible:
        st.info(tr('Geen shiften met deze status.'))
        return
    selected = st.selectbox(tr('Shift selecteren'), [e['id'] for e in eligible], format_func=translated_formatter(lambda i: next((tr('{v0} · {v1:%d-%m-%Y %H:%M} → {v2}', v0=e['name'], v1=e['start'].astimezone(tz), v2=e['end'].astimezone(tz).strftime('%d-%m-%Y %H:%M') if e['end'] else tr('Nog bezig')) for e in eligible if e['id'] == i))))
    entry = next(e for e in eligible if e['id'] == selected)
    if entry['user_id'] == me['id']:
        st.info(tr('Je mag je eigen shift niet corrigeren of goedkeuren. Vraag een andere bevoegde beheerder.'))
    else:
        with st.form(f"review_{entry['id']}_{entry['version']}"):
            action = st.selectbox(tr('Shiftactie'), ['Corrigeren'] if entry['end'] is None or entry['review_status'] == 'approved' else ['Goedkeuren', 'Corrigeren'], format_func=tr)
            start = entry['start'].astimezone(tz)
            end = (entry['end'] or datetime.now(tz)).astimezone(tz)
            a, b = st.columns(2)
            with a:
                start_date = st.date_input(tr('Begindatum'), value=start.date())
                start_time = st.time_input(tr('Begintijd'), value=start.time(), step=60)
            with b:
                end_date = st.date_input(tr('Einddatum'), value=end.date())
                end_time = st.time_input(tr('Eindtijd'), value=end.time(), step=60)
            reason = st.text_area(tr('Reden / opmerking (verplicht bij corrigeren)'), max_chars=500)
            st.caption(tr('Bij Goedkeuren worden de opgeslagen tijden goedgekeurd; gewijzigde tijdvelden gelden alleen bij Corrigeren. Een correctie moet daarna apart goedgekeurd worden.'))
            if st.form_submit_button(tr('Shiftactie bevestigen'), type='primary'):
                result = run(lambda: api.review_shift(token, branch_id, entry['id'], entry['version'], 'approve' if action == 'Goedkeuren' else 'correct', reason, datetime.combine(start_date, start_time, tzinfo=tz), datetime.combine(end_date, end_time, tzinfo=tz)), 'Shift goedgekeurd.' if action == 'Goedkeuren' else 'Correctie opgeslagen. De shift wacht opnieuw op goedkeuring.')
                if result:
                    st.rerun()
    with st.expander(tr('Historiek van deze shift')):
        history = run(lambda: api.shift_history(token, branch_id, entry['id']))
        if history:
            st.dataframe(translated_table(history), hide_index=True, use_container_width=True)
        else:
            st.info(tr('Nog geen correcties of goedkeuringen geregistreerd.'))
