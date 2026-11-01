from datetime import datetime, timedelta
import streamlit as st

from workforce.i18n import tr, translated_formatter, translated_table
from workforce.reports import period_bounds


def _rule_label(rule, tz):
    local = rule["start"].astimezone(tz)
    suffix = tr(" · wekelijks") if rule["weekly"] else ""
    return local.strftime("%d-%m-%Y %H:%M") + suffix


def show_my_availability(api, token, branch_id, tz, run):
    st.subheader(tr("Mijn beschikbaarheid"))
    st.write(tr(
        "Geef aan wanneer je kunt werken. Dit zijn voorkeuren: je bent pas ingepland wanneer een manager een shift aanmaakt."
    ))
    rules = run(lambda: api.availability_rules(token, branch_id)) or []

    if rules:
        st.dataframe(translated_table([
            {
                "Dag": r["start"].astimezone(tz).strftime("%A %d-%m-%Y"),
                "Vanaf": r["start"].astimezone(tz).strftime("%H:%M"),
                "Tot": r["end"].astimezone(tz).strftime("%H:%M"),
                "Herhaling": "Wekelijks" if r["weekly"] else "Eenmalig",
                "Herhalen tot": r["recurrence_until"] if r["weekly"] else None,
            }
            for r in rules
        ]), hide_index=True, use_container_width=True)
    else:
        st.info(tr("Je hebt nog geen beschikbaarheden opgegeven."))

    selected = st.selectbox(
        tr("Beschikbaarheid toevoegen of wijzigen"),
        [None] + [r["id"] for r in rules],
        format_func=translated_formatter(
            lambda i: tr("Nieuw tijdsblok") if i is None else _rule_label(next(r for r in rules if r["id"] == i), tz)
        ),
    )
    old = next((r for r in rules if r["id"] == selected), None)
    base_start = old["start"].astimezone(tz) if old else datetime.combine(
        datetime.now(tz).date() + timedelta(days=1),
        datetime.strptime("09:00", "%H:%M").time(),
        tzinfo=tz,
    )
    base_end = old["end"].astimezone(tz) if old else base_start + timedelta(hours=8)

    with st.form(f"availability_{selected or 'new'}"):
        day = st.date_input(tr("Beschikbare dag"), value=base_start.date())
        a, b = st.columns(2)
        with a:
            start_time = st.time_input(tr("Vanaf"), value=base_start.time().replace(tzinfo=None), step=900)
        with b:
            end_time = st.time_input(tr("Tot"), value=base_end.time().replace(tzinfo=None), step=900)
        weekly = st.checkbox(tr("Elke week herhalen"), value=bool(old and old["weekly"]))
        repeat_default = old["recurrence_until"] if old and old["weekly"] else day + timedelta(weeks=8)
        repeat_until = st.date_input(tr("Herhalen tot"), value=repeat_default, disabled=not weekly)
        if st.form_submit_button(tr("Beschikbaarheid opslaan"), type="primary"):
            start_at = datetime.combine(day, start_time, tzinfo=tz)
            end_at = datetime.combine(day, end_time, tzinfo=tz)
            if run(
                lambda: api.save_availability(
                    token,
                    branch_id,
                    start_at,
                    end_at,
                    weekly,
                    repeat_until if weekly else None,
                    selected,
                    old["version"] if old else None,
                ),
                "Beschikbaarheid opgeslagen.",
            ):
                st.rerun()

    if old:
        if st.button(tr("Geselecteerde beschikbaarheid verwijderen")):
            if run(
                lambda: api.delete_availability(token, branch_id, old["id"], old["version"]),
                "Beschikbaarheid verwijderd.",
            ):
                st.rerun()


def show_team_availability(api, token, branch_id, tz, zone, run):
    st.subheader(tr("Beschikbaarheden"))
    st.write(tr("Bekijk wanneer medewerkers hebben aangegeven dat ze kunnen werken. Beschikbaarheid maakt nooit automatisch een shift."))
    day = st.date_input(tr("Datum beschikbaarheden"), value=datetime.now(tz).date(), key="availability_period_day")
    period = st.selectbox(tr("Periode"), ["Dag", "Week", "Maand"], index=1, format_func=tr, key="availability_period")
    begin, end = period_bounds(day, period, zone)
    slots = run(lambda: api.availability_occurrences(token, branch_id, begin, end, team=True))
    if slots is None:
        return
    if not slots:
        st.info(tr("Geen beschikbaarheden in deze periode."))
        return

    rows = []
    for slot in slots:
        warnings = []
        if slot["absence_conflict"]:
            warnings.append(tr("conflict met afwezigheid"))
        if slot["shift_conflict"]:
            warnings.append(tr("overlapt bestaande shift"))
        rows.append({
            "Medewerker": slot["name"],
            "Begin": slot["start"].astimezone(tz),
            "Einde": slot["end"].astimezone(tz),
            "Herhaling": "Wekelijks" if slot["weekly"] else "Eenmalig",
            "Waarschuwing": " · ".join(warnings),
        })
    st.dataframe(translated_table(rows), hide_index=True, use_container_width=True)

    grouped = {}
    for slot in slots:
        key = (slot["start"], slot["end"])
        grouped.setdefault(key, []).append(slot["name"])
    st.subheader(tr("Medewerkers per tijdsblok"))
    st.dataframe([
        {
            "Begin": start.astimezone(tz),
            "Einde": end_at.astimezone(tz),
            "Beschikbare medewerkers": ", ".join(sorted(names)),
        }
        for (start, end_at), names in sorted(grouped.items())
    ], hide_index=True, use_container_width=True)
