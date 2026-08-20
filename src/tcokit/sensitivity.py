"""Which input actually decides the answer.

A TCO comparison produces one number and it always looks authoritative. The
honest follow-up is that the number rests on a dozen assumptions, several of
which nobody knows precisely. Sensitivity analysis is how a model says so out
loud: vary one input at a time across a plausible range, hold everything else,
and report how far the answer moves.

The output is deliberately ordered by how much each input matters, because the
useful sentence at the end of an analysis is rarely "electrification saves
X dollars". It is "the answer is decided by the diesel price and the incentive,
and it is barely affected by maintenance, so those are the two numbers worth
arguing about."
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal

from .inputs import Policy, Region, Scenario, Vehicle
from .money import money
from .tco import Comparison, compute


@dataclass(frozen=True)
class Swing:
    """How far the comparison moves when one input is varied."""

    input_name: str
    low_label: str
    high_label: str
    low_difference: Decimal
    high_difference: Decimal

    @property
    def swing(self) -> Decimal:
        return abs(self.high_difference - self.low_difference)

    @property
    def changes_the_decision(self) -> bool:
        """True when the sign flips, i.e. the recommendation itself changes."""
        return (self.low_difference < 0) != (self.high_difference < 0)


def _difference(diesel: Vehicle, electric: Vehicle, r: Region, p: Policy, s: Scenario) -> Decimal:
    return Comparison(compute(diesel, r, p, s), compute(electric, r, p, s)).difference


def tornado(diesel: Vehicle, electric: Vehicle, region: Region, policy: Policy,
            scenario: Scenario, variation: Decimal = Decimal("0.25")) -> list[Swing]:
    """Vary each major input up and down, ordered by how much it matters.

    `variation` is a fraction, so 0.25 means each input is tested at 75 percent
    and 125 percent of its stated value. Inputs left at zero are skipped rather
    than reported as insensitive, because a lever that is switched off is not
    the same finding as a lever that does not matter.
    """
    v = money(variation)
    lo, hi = Decimal(1) - v, Decimal(1) + v
    out: list[Swing] = []

    def add(name: str, low_r=None, high_r=None, low_p=None, high_p=None,
            low_s=None, high_s=None, low_e=None, high_e=None):
        d_low = _difference(diesel, low_e or electric, low_r or region,
                            low_p or policy, low_s or scenario)
        d_high = _difference(diesel, high_e or electric, high_r or region,
                             high_p or policy, high_s or scenario)
        out.append(Swing(name, f"-{int(v*100)}%", f"+{int(v*100)}%", d_low, d_high))

    if region.diesel_price_per_gallon:
        add("Diesel price",
            low_r=replace(region, diesel_price_per_gallon=region.diesel_price_per_gallon * lo),
            high_r=replace(region, diesel_price_per_gallon=region.diesel_price_per_gallon * hi))
    if region.electricity_price_per_kwh:
        add("Electricity price",
            low_r=replace(region, electricity_price_per_kwh=region.electricity_price_per_kwh * lo),
            high_r=replace(region, electricity_price_per_kwh=region.electricity_price_per_kwh * hi))
    if policy.purchase_incentive:
        add("Purchase incentive",
            low_p=replace(policy, purchase_incentive=policy.purchase_incentive * lo),
            high_p=replace(policy, purchase_incentive=policy.purchase_incentive * hi))
    if policy.road_user_charge_per_mile:
        add("Road user charge",
            low_p=replace(policy, road_user_charge_per_mile=policy.road_user_charge_per_mile * lo),
            high_p=replace(policy, road_user_charge_per_mile=policy.road_user_charge_per_mile * hi))
    if policy.carbon_tax_per_gallon:
        add("Carbon tax",
            low_p=replace(policy, carbon_tax_per_gallon=policy.carbon_tax_per_gallon * lo),
            high_p=replace(policy, carbon_tax_per_gallon=policy.carbon_tax_per_gallon * hi))
    add("Annual mileage",
        low_s=replace(scenario, annual_miles=scenario.annual_miles * lo),
        high_s=replace(scenario, annual_miles=scenario.annual_miles * hi))
    add("Electric purchase price",
        low_e=replace(electric, purchase_price=electric.purchase_price * lo),
        high_e=replace(electric, purchase_price=electric.purchase_price * hi))
    if electric.kwh_per_mile:
        add("Electric consumption",
            low_e=replace(electric, kwh_per_mile=electric.kwh_per_mile * lo),
            high_e=replace(electric, kwh_per_mile=electric.kwh_per_mile * hi))

    return sorted(out, key=lambda s: s.swing, reverse=True)


def incentive_to_breakeven(diesel: Vehicle, electric: Vehicle, region: Region,
                           policy: Policy, scenario: Scenario,
                           ceiling: Decimal = Decimal("500000"),
                           step: Decimal = Decimal("500")) -> Decimal | None:
    """Smallest purchase incentive at which the electric vehicle wins.

    This is the question a ministry actually asks: not "is it cheaper" but
    "how much would we have to put on the table to make it cheaper". Searched
    by increments rather than solved algebraically because the incentive is
    capped at the vehicle's capital cost, which makes the relationship
    piecewise rather than linear.
    """
    step, ceiling = money(step), money(ceiling)
    amount = Decimal(0)
    while amount <= ceiling:
        trial = replace(policy, purchase_incentive=amount)
        if _difference(diesel, electric, region, trial, scenario) <= 0:
            return amount
        amount += step
    return None
