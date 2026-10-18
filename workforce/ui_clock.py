"""Explain clock availability without weakening the server's clock policy."""
import streamlit as st
from workforce.clock_policy import clock_in_allowed, clock_in_opens_at
from workforce.i18n import tr


def show_clock_availability(plans, active, snapshot, tz):
    choices = [p for p in plans if p['status'] == 'scheduled' and p['entry_id'] is None
               and clock_in_allowed(p['start'], p['end'], snapshot, tz)]
    st.caption(tr('Je kunt alleen op de begindag van je ingeplande shift inklokken, vanaf 10 minuten voor de start.'))
    if active:
        st.success(tr('Je bent ingeklokt sinds {v0}.', v0=active['start'].astimezone(tz).strftime('%d-%m-%Y %H:%M')))
        st.caption(tr('Klaar met werken? Klik op Uitklokken. Je uren wachten daarna op controle.'))
    elif choices:
        st.success(tr('Je kunt nu inklokken voor je ingeplande shift.'))
    else:
        future = [p for p in plans if p['status'] == 'scheduled' and p['entry_id'] is None
                  and p['end'] > snapshot and p['start'].astimezone(tz).date() >= snapshot.astimezone(tz).date()]
        if future:
            upcoming = min(future, key=lambda p: p['start'])
            st.info(tr('Volgende shift: {v0} tot {v1}.',
                       v0=upcoming['start'].astimezone(tz).strftime('%d-%m-%Y %H:%M'),
                       v1=upcoming['end'].astimezone(tz).strftime('%d-%m-%Y %H:%M')))
            st.write(tr('Inklokken mogelijk vanaf {v0}.',
                        v0=clock_in_opens_at(upcoming['start'], tz).astimezone(tz).strftime('%d-%m-%Y %H:%M')))
        else:
            st.info(tr('Er is nu geen ingeplande shift waarvoor je kunt inklokken. Bekijk je planning of vraag je beheerder.'))
    return choices
