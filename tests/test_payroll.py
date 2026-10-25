from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from concurrent.futures import ThreadPoolExecutor
import pytest
from sqlalchemy import select
from workforce.models import WorkEntry, SalaryRate
from workforce.payroll import salary_amount, base_pay
from workforce.reports import period_bounds
from workforce.service import Denied, now
from test_ui import app_for


def entry(api, team, start, end, approved=True):
    with api.sessions.begin() as session:
        session.add(WorkEntry(branch_id=team['branch'], user_id=team['worker'], started_at=start, ended_at=end,
            review_status='approved' if approved else 'pending', version=1,
            reviewed_by=team['owner'] if approved else None, reviewed_at=end if approved else None))


def worker(api, team, month=date(2026, 10, 1)):
    return next(r for r in api.monthly_payroll(team['ot'], team['branch'], month) if r['user_id'] == team['worker'])


def test_hourly_uses_approved_elapsed_time_and_clips_month_boundaries(api, team):
    month = date(2026, 10, 1)
    begin, end = period_bounds(month, 'Maand')
    api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'hourly', '20,00', 'gross', month)
    entry(api, team, begin-timedelta(hours=1), begin+timedelta(hours=1))
    tz = ZoneInfo('Europe/Brussels')
    entry(api, team, datetime(2026, 10, 25, 1, 30, tzinfo=tz), datetime(2026, 10, 25, 3, 30, tzinfo=tz))
    entry(api, team, end-timedelta(hours=1), end+timedelta(hours=1))
    entry(api, team, begin+timedelta(days=2), begin+timedelta(days=2, hours=1), approved=False)
    result = worker(api, team)
    assert result['approved_hours'] == 5
    assert result['pending_hours'] == 1
    assert result['amount'] == Decimal('100.00')


def test_active_and_pending_hours_are_not_payable(api, team):
    month = (now().date().replace(day=1)-timedelta(days=1)).replace(day=1)
    begin, _ = period_bounds(month, 'Maand')
    current = begin+timedelta(days=10, hours=12)
    api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'hourly', '18', 'net', month)
    entry(api, team, current-timedelta(hours=2), current-timedelta(hours=1))
    entry(api, team, current-timedelta(minutes=50), current-timedelta(minutes=30), approved=False)
    entry(api, team, current-timedelta(minutes=10), None, approved=False)
    result = worker(api, team, month)
    assert result['amount'] == Decimal('18.00')
    assert result['pending_hours'] > 0 and result['active_hours'] > 0


def test_monthly_salary_and_new_month_rate_preserve_previous_month(api, team):
    api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'monthly', '3000', 'gross', date(2026, 10, 1))
    assert worker(api, team)['amount'] == Decimal('3000.00')
    api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'hourly', '25', 'net', date(2026, 11, 1))
    assert worker(api, team)['amount'] == Decimal('3000.00')
    assert worker(api, team, date(2026, 11, 1))['rate']['amount'] == Decimal('25.00')
    assert worker(api, team, date(2026, 9, 1))['amount'] is None


def test_salary_is_private_to_owners_and_platform(api, team):
    api.set_role(team['ot'], team['branch'], team['worker'], 'admin')
    for token in (team['wt'], team['xt']):
        with pytest.raises(Denied):
            api.monthly_payroll(token, team['branch'], date(2026, 10, 1))
        with pytest.raises(Denied):
            api.set_salary_rate(token, team['branch'], team['worker'], 'hourly', '20', 'gross', date(2026, 10, 1))
    with pytest.raises(ValueError):
        api.set_salary_rate(team['ot'], team['branch'], team['other'], 'hourly', '20', 'gross', date(2026, 10, 1))
    assert api.monthly_payroll(team['pt'], team['branch'], date(2026, 10, 1))
    api.logout(team['ot'])
    with pytest.raises(Denied):
        api.monthly_payroll(team['ot'], team['branch'], date(2026, 10, 1))


def test_salary_amounts_do_not_enter_shared_audit_and_history_blocks_account_deletion(api, team):
    api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'hourly', '123.45', 'gross', date(2026, 10, 1))
    events = api.audit(team['ot'], team['branch'])
    assert any(e['actie'] == 'salary.changed' for e in events)
    assert all('123.45' not in e['detail'] for e in events)
    with pytest.raises(Denied):
        api.delete_unused_account(team['pt'], team['worker'])


def test_duplicate_saves_update_one_monthly_setting(api, team):
    def save(amount):
        return api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'hourly', amount, 'gross', date(2026, 10, 1))
    with ThreadPoolExecutor(max_workers=2) as pool:
        ids = list(pool.map(save, ['20', '21']))
    assert ids[0] == ids[1]
    with api.sessions() as session:
        assert len(list(session.scalars(select(SalaryRate)))) == 1


def test_historical_fixed_salary_requires_contract_check_after_revocation(api, team):
    month = date(2026, 10, 1)
    begin, end = period_bounds(month, 'Maand')
    api.set_salary_rate(team['ot'], team['branch'], team['worker'], 'monthly', '3000', 'gross', month)
    entry(api, team, begin+timedelta(hours=1), begin+timedelta(hours=3))
    api.set_role(team['ot'], team['branch'], team['worker'], None)
    row = worker(api, team)
    assert row['approved_hours'] == 2 and row['needs_contract_check']
    assert row['amount'] is None


@pytest.mark.parametrize('bad', ['NaN', 'Infinity', '-1', '0', '1.001', '1000000.01', None, True, 'twenty'])
def test_invalid_salary_values(bad):
    with pytest.raises(ValueError):
        salary_amount(bad)


def test_exact_seconds_are_rounded_only_after_calculation():
    assert base_pay('hourly', Decimal('18'), Decimal('1')) == Decimal('0.01')
    assert base_pay('hourly', Decimal('18'), Decimal('20')) == Decimal('0.10')


def test_salary_ui_saves_and_shows_calculated_month(api, team, engine, monkeypatch):
    app = app_for(team['ot'], engine, monkeypatch)
    app.button(key='manager_open_Lonen').click().run()
    assert not app.exception
    next(s for s in app.selectbox if s.label == 'Medewerker voor looninstelling').set_value(team['worker']).run()
    next(n for n in app.number_input if n.label == 'Afgesproken bedrag in euro').set_value(20.0)
    next(b for b in app.button if b.label == 'Loonafspraak opslaan').click().run()
    assert not app.exception
    row = worker(api, team, now().date().replace(day=1))
    assert row['rate']['amount'] == Decimal('20.00')
    table = app.dataframe[0].value
    assert table.loc[table['Medewerker'] == 'Worker', 'Tarief'].iloc[0] == '€ 20,00'
    api.set_role(team['ot'], team['branch'], team['worker'], 'admin')
    staff = app_for(team['wt'], engine, monkeypatch)
    assert 'Lonen' not in staff.radio(key=f"branch_page_{team['branch']}").options
