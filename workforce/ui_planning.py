from datetime import datetime, timedelta
import streamlit as st
from workforce.reports import period_bounds


def show_planning(api,token,branch_id,admin,tz,zone,run):
    st.subheader('Shiftplanning')
    st.write('Bekijk geplande diensten en vergelijk ze met de gekoppelde tijdregistratie.')
    plans=run(lambda: api.plans(token,branch_id,team=admin))
    if plans is None:
        return
    day=st.date_input('Datum voor planning',value=datetime.now(tz).date())
    period=st.selectbox('Planningperiode',['Dag','Week','Maand'],index=1)
    begin,end=period_bounds(day,period,zone)
    visible=[p for p in plans if p['start']<end and p['end']>begin]
    rows=[]
    for p in visible:
        planned=(p['end']-p['start']).total_seconds()/3600
        actual=(p['actual_end']-p['actual_start']).total_seconds()/3600 if p['actual_end'] else None
        rows.append({'Medewerker':p['name'],'Begin':p['start'].astimezone(tz),'Einde':p['end'].astimezone(tz),'Status':'Geannuleerd' if p['status']=='cancelled' else 'Gepland','Geplande uren':round(planned,2),'Geregistreerde uren':round(actual,2) if actual is not None else None,'Verschil (uur)':round(actual-planned,2) if actual is not None else None,'Opmerking':p['note']})
    if rows:
        st.dataframe(rows,hide_index=True,use_container_width=True)
    else:
        st.info('Nog geen shiften gepland in deze periode.')
    st.caption('Geregistreerde uren kunnen nog op controle wachten. Goedkeuring gebeurt via Shiften controleren; planning keurt geen uren automatisch goed.')
    if not admin:
        return
    members=run(lambda: api.members(token,branch_id)) or []
    members=[m for m in members if m['role']!='revoked' and m['active']]
    if not members:
        st.info('Koppel eerst een actieve medewerker via Team & rechten.')
        return
    with st.expander('Shift toevoegen of wijzigen'):
        editable=[p for p in plans if p['status']=='scheduled' and p['entry_id'] is None]
        selected=st.selectbox('Geplande shift bewerken',[None]+[p['id'] for p in editable],format_func=lambda i: 'Nieuwe shift' if i is None else next(f"{p['name']} · {p['start'].astimezone(tz):%d-%m-%Y %H:%M}" for p in editable if p['id']==i))
        old=next((p for p in editable if p['id']==selected),None)
        start=old['start'].astimezone(tz) if old else datetime.now(tz)+timedelta(days=1)
        stop=old['end'].astimezone(tz) if old else start+timedelta(hours=4)
        ids=[m['id'] for m in members]
        if old and old['user_id'] not in ids:
            st.info('Deze medewerker is niet meer actief; annuleer de planning hieronder.')
        else:
            with st.form(f'plan_{selected}_{old["version"] if old else 0}'):
                uid=st.selectbox('Medewerker inplannen',ids,index=ids.index(old['user_id']) if old else 0,disabled=old is not None,format_func=lambda i:next(f"{m['name']} · {m['email']}" for m in members if m['id']==i))
                a,b=st.columns(2)
                with a:
                    sd=st.date_input('Geplande begindatum',value=start.date())
                    stime=st.time_input('Geplande begintijd',value=start.time(),step=60)
                with b:
                    ed=st.date_input('Geplande einddatum',value=stop.date())
                    etime=st.time_input('Geplande eindtijd',value=stop.time(),step=60)
                note=st.text_input('Opmerking bij planning',value=old['note'] if old else '',max_chars=500)
                if st.form_submit_button('Planning opslaan'):
                    if run(lambda:api.save_plan(token,branch_id,uid,datetime.combine(sd,stime,tzinfo=tz),datetime.combine(ed,etime,tzinfo=tz),note,selected,old['version'] if old else None),'Planning opgeslagen.'):
                        st.rerun()
        if old:
            with st.form(f'cancel_plan_{selected}'):
                reason=st.text_input('Reden annulering')
                if st.form_submit_button('Geplande shift annuleren'):
                    if run(lambda:api.cancel_plan(token,branch_id,selected,old['version'],reason),'Geplande shift geannuleerd.'):
                        st.rerun()


def show_alerts(api,token,branch_id,admin,run):
    st.subheader('Meldingen')
    st.caption('Deze meldingen worden bij openen of verversen berekend. Er zijn geen automatische pushberichten of automatische uitklokacties.')
    alerts=run(lambda:api.alerts(token,branch_id,team=admin))
    if alerts:
        for a in alerts:
            if a['type']=='uitklokken':
                st.warning(f"{a['medewerker']}: {a['melding']}")
            else:
                st.info(f"{a['medewerker']}: {a['melding']}")
    elif alerts is not None:
        st.success('Geen openstaande meldingen.')
    st.write('Vergeten uitklokken: meer dan 15 minuten na de gekoppelde geplande eindtijd, of meer dan 12 uur ingeklokt zonder zo’n afwijking. Controleer de werkelijke tijden voordat je uren goedkeurt.')
    if admin:
        st.write('Gebruik Shiften controleren voor correcties en goedkeuringen.')
    if st.button('Meldingen verversen'):
        st.rerun()
