"""Presentation of authorized time entries; never loads data across users."""
def shift_rows(entries, begin, end, tz, as_of):
    rows = []
    for entry in entries:
        stop = entry['end'] or as_of
        if entry['start'] >= end or stop < begin:
            continue
        rows.append({
            'Datum': entry['start'].astimezone(tz).strftime('%d-%m-%Y'),
            'Ingeklokt': entry['start'].astimezone(tz).strftime('%d-%m-%Y %H:%M'),
            'Uitgeklokt': entry['end'].astimezone(tz).strftime('%d-%m-%Y %H:%M') if entry['end'] else 'Nog bezig',
            'Status': 'Bezig' if entry['end'] is None else ('Goedgekeurd' if entry.get('review_status') == 'approved' else 'Wacht op controle'),
            'Duur volledige shift (uur)': round(max(0, (stop-entry['start']).total_seconds()) / 3600, 2),
        })
    return rows
