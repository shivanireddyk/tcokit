"""Money and unit discipline for total cost of ownership work.

A TCO model is an argument about money made to someone who can act on it: a
fleet operator deciding what to buy, or a transport ministry deciding what to
subsidise. Two things ruin that argument quietly.

The first is binary floating point. A fuel price of $3.85 a gallon is not
representable in binary, so a model that runs it through float accumulates
error across twenty years of discounted cash flows. The error is small, but it
is not zero, and "small" is not a property you want to have to explain when
someone asks why two runs of the same scenario differ in the last cent. Every
monetary quantity here is a Decimal, and floats are rejected at the boundary.

The second is units. Diesel is priced in dollars per gallon and consumed in
miles per gallon. Electricity is priced in dollars per kilowatt hour and
consumed in kilowatt hours per mile. Those are reciprocal relationships and it
is genuinely easy to invert one by accident. The conversion is therefore done
in one place, named explicitly, and tested.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


class UnitError(ValueError):
    """A quantity was given in a unit the model cannot use."""


def money(value: Decimal | int | str) -> Decimal:
    """Coerce a value to Decimal money, refusing floats.

    Floats are rejected rather than converted because the conversion is where
    the error enters. Decimal(0.1) is 0.1000000000000000055511151231257827,
    and that is the number the model would then use for twenty years.
    """
    if isinstance(value, float):
        raise TypeError(
            "money must be Decimal, int or str, not float. "
            'Write money("3.85") rather than money(3.85) so the figure in the '
            "scenario file is the figure in the arithmetic."
        )
    return value if isinstance(value, Decimal) else Decimal(str(value))


def to_cents(value: Decimal) -> Decimal:
    """Round to cents for display only. Never round inside a calculation."""
    return money(value).quantize(CENTS, rounding=ROUND_HALF_UP)


def diesel_cost_per_mile(price_per_gallon: Decimal, miles_per_gallon: Decimal) -> Decimal:
    """Dollars per mile for a liquid-fuelled vehicle.

    price is $/gal, efficiency is mi/gal, so the cost is price / efficiency.
    Naming both sides here is the point: the inverse is a plausible-looking
    number and would be wrong by the square of the efficiency.
    """
    mpg = money(miles_per_gallon)
    if mpg <= 0:
        raise UnitError("miles per gallon must be positive")
    return money(price_per_gallon) / mpg


def electric_cost_per_mile(price_per_kwh: Decimal, kwh_per_mile: Decimal) -> Decimal:
    """Dollars per mile for a battery-electric vehicle.

    price is $/kWh and consumption is kWh/mile, so the cost is the product,
    not the quotient. This is the reciprocal of the diesel case and it is the
    single easiest thing to invert in a TCO model.
    """
    kwh = money(kwh_per_mile)
    if kwh <= 0:
        raise UnitError("kilowatt hours per mile must be positive")
    return money(price_per_kwh) * kwh


def present_value(amount: Decimal, year: int, discount_rate: Decimal) -> Decimal:
    """Discount a future amount back to year zero.

    Year 0 is undiscounted. A cost in year n is divided by (1 + r)^n. The
    discount rate is what makes a purchase incentive today worth more than the
    same money spread across the vehicle's life, which is usually the whole
    argument a policy analyst is making.
    """
    if year < 0:
        raise ValueError("year must not be negative")
    r = money(discount_rate)
    if r <= -1:
        raise ValueError("discount rate must be greater than -1")
    return money(amount) / ((Decimal(1) + r) ** year)
