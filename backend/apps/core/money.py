"""Money helpers. Always Decimal, never float."""
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal("0.00")
HUNDRED = Decimal("100")


def q2(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def q3(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def line_tax(amount_after_discount: Decimal, rate: Decimal, *, inclusive: bool, applicable: bool):
    """Return (taxable_value, tax, payable_total) for one line.

    inclusive=True : `amount` already contains tax -> back-calculate.
    inclusive=False: tax is added on top.
    applicable=False (composition / unregistered): no tax at all.
    """
    amount = q2(amount_after_discount)
    if not applicable or rate == 0:
        return amount, ZERO, amount
    rate = Decimal(rate)
    if inclusive:
        taxable = q2(amount * HUNDRED / (HUNDRED + rate))
        return taxable, q2(amount - taxable), amount
    tax = q2(amount * rate / HUNDRED)
    return amount, tax, q2(amount + tax)
