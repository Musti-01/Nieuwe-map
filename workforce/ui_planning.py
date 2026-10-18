from workforce.i18n import tr, translated_formatter, translated_table
from datetime import datetime, timedelta
import streamlit as st
from workforce.reports import period_bounds


def show_planning(api,token,branch_id,admin,tz,zone,run):
    st.subheader(tr('Shiftplanning'))
    st.write(tr('Bekijk geplande diensten en vergelijk ze met de gekoppelde tijdregistratie.'))
    plans=run(lambda: api.plans(token,branch_id,team=admin))
    if plans is None:
        return
    day=st.date_input(tr('Datum voor planning'),value=datetime.now(tz).date())
    period=st.selectbox(tr('Planningperiode'),['Dag','Week','Maand'],index=1, format_func=tr)
    begin,end=period_bounds(day,period,zone)
    visible=[p for p in plans if p['start']<end and p['end']>begin]
    rows=[]
    for p in visible:
        planned=(p['end']-p['start']).total_seconds()/3600
        actual=(p['actual_end']-p['actual_start']).total_seconds()/3600 if p['actual_end'] else None
        rows.append({'Medewerker':p['name'],'Begin':p['start'].astimezone(tz),'Einde':p['end'].astimezone(tz),'Status':'Geannuleerd' if p['status']=='cancelled' else 'Gepland','Geplande uren':round(planned,2),'Geregistreerde uren':round(actual,2) if actual is not None else None,'Verschil (uur)':round(actual-planned,2) if actual is not None else None,'Opmerking':p['note']})
    if rows:
        st.dataframe(translated_table(rows),hide_index=True,use_container_width=True)
    else:
        st.info(tr('Nog geen shiften gepland in deze periode.'))
    st.caption(tr('Geregistreerde uren kunnen nog op controle wachten. Goedkeuring gebeurt via Shiften controleren; planning keurt geen uren automatisch goed.'))
    if not admin:
        return
    members=run(lambda: api.members(token,branch_id)) or []
    members=[m for m in members if m['role']!='revoked' and m['active']]
    if not members:
        st.info(tr('Koppel eerst een actieve medewerker via Medewerkers & rechten.'))
        return
    with st.expander(tr('Shift toevoegen of wijzigen'), expanded=True):
        editable=[p for p in plans if p['status']=='scheduled' and p['entry_id'] is None]
        selected=st.selectbox(tr('Geplande shift bewerken'),[None]+[p['id'] for p in editable],format_func=translated_formatter(lambda i: tr('Nieuwe shift') if i is None else next((tr('{v0} · {v1:%d-%m-%Y %H:%M}', v0=p['name'], v1=p['start'].astimezone(tz)) for p in editable if p['id'] == i))))
        old=next((p for p in editable if p['id']==selected),None)
        start=old['start'].astimezone(tz) if old else datetime.combine(day, datetime.now(tz).time().replace(second=0, microsecond=0), tzinfo=tz)
        stop=old['end'].astimezone(tz) if old else start+timedelta(hours=4)
        ids=[m['id'] for m in members]
        if old and old['user_id'] not in ids:
            st.info(tr('Deze medewerker is niet meer actief; annuleer de planning hieronder.'))
        else:
            with st.form(f'plan_{selected}_{old["version"] if old else 0}'):
                uid=st.selectbox(tr('Medewerker inplannen'),ids,index=ids.index(old['user_id']) if old else 0,disabled=old is not None,format_func=translated_formatter(lambda i: next((tr('{v0} · {v1}', v0=m['name'], v1=m['email']) for m in members if m['id'] == i))))
                a,b=st.columns(2)
                with a:
                    sd=st.date_input(tr('Geplande begindatum'),value=start.date())
                    stime=st.time_input(tr('Geplande begintijd'),value=start.time(),step=60)
                with b:
                    ed=st.date_input(tr('Geplande einddatum'),value=stop.date())
                    etime=st.time_input(tr('Geplande eindtijd'),value=stop.time(),step=60)
                note=st.text_input(tr('Opmerking bij planning'),value=old['note'] if old else '',max_chars=500)
                if st.form_submit_button(tr('Planning opslaan')):
                    if run(lambda:api.save_plan(token,branch_id,uid,datetime.combine(sd,stime,tzinfo=tz),datetime.combine(ed,etime,tzinfo=tz),note,selected,old['version'] if old else None),'Planning opgeslagen.'):
                        st.rerun()
        if old:
            with st.form(f'cancel_plan_{selected}'):
                reason=st.text_input(tr('Reden annulering'))
                if st.form_submit_button(tr('Geplande shift annuleren')):
                    if run(lambda:api.cancel_plan(token,branch_id,selected,old['version'],reason),'Geplande shift geannuleerd.'):
                        st.rerun()


def show_alerts(api,token,branch_id,admin,run):
    st.subheader(tr('Meldingen'))
    st.caption(tr('Deze meldingen worden bij openen of verversen berekend. Er zijn geen automatische pushberichten of automatische uitklokacties.'))
    alerts=run(lambda:api.alerts(token,branch_id,team=admin))
    if alerts:
        for a in alerts:
            if a['type']=='uitklokken':
                st.warning(tr('{v0}: {v1}', v0=a['medewerker'], v1=tr(a['melding'])))
            else:
                st.info(tr('{v0}: {v1}', v0=a['medewerker'], v1=tr(a['melding'])))
            if admin:
                from workforce.ui_navigation import open_shift_review
                st.button(tr('Shift bekijken en controleren'), key=f"alert_review_{a['shift']}", on_click=open_shift_review, args=(branch_id, a['shift']))
    elif alerts is not None:
        st.success(tr('Geen openstaande meldingen.'))
    st.write(tr('Vergeten uitklokken: meer dan 15 minuten na de gekoppelde geplande eindtijd, of meer dan 12 uur ingeklokt zonder zo’n afwijking. Controleer de werkelijke tijden voordat je uren goedkeurt.'))
    if admin:
        st.write(tr('Gebruik Shiften controleren voor correcties en goedkeuringen.'))
    if st.button(tr('Meldingen verversen')):
        st.rerun()
