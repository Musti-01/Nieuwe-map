"""Monthly base-pay arithmetic using exact decimal amounts and elapsed time."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import timezone

CENT = Decimal('0.01')


def salary_amount(value):
    try:
        if isinstance(value, bool):
            raise ValueError
        amount = Decimal(str(value).strip().replace(',', '.'))
        if not amount.is_finite() or amount <= 0 or amount > Decimal('1000000') or amount != amount.quantize(CENT):
            raise ValueError
        return amount.quantize(CENT)
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError('Geef een positief loonbedrag met maximaal twee decimalen en maximaal 1.000.000 euro.') from None


def elapsed_seconds(start, end):
    delta = end.astimezone(timezone.utc)-start.astimezone(timezone.utc)
    return Decimal(delta.days*86400+delta.seconds) + Decimal(delta.microseconds)/Decimal(1000000)


def base_pay(kind, amount, seconds):
    if kind == 'hourly':
        return (amount*seconds/Decimal(3600)).quantize(CENT, rounding=ROUND_HALF_UP)
    if kind == 'monthly':
        return amount.quantize(CENT, rounding=ROUND_HALF_UP)
    raise ValueError('Kies uurloon of vast maandloon.')


def euros(amount):
    return '€ ' + f'{amount:,.2f}'.replace(',', '_').replace('.', ',').replace('_', '.')
