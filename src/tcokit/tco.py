"""The cost engine: annual cash flows, discounted, with the reasoning kept.

The output of this module is deliberately not a single number. A fleet operator
asking "should I buy the electric truck" and a ministry asking "which lever
moves the market" need the same arithmetic broken down differently, and both
need to see which component dominates. So a result carries its cost lines, its
year-by-year cash flow, and the crossover year, not just a total.

One structural decision worth stating: capital is spent in year 0 and residual
value is recovered in the final year, discounted back. Everything else is an
annual flow. That means a purchase incentive is worth its full face value while
a per-mile road charge is worth less than its undiscounted sum, which is
exactly the asymmetry a policy analyst is trying to quantify.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from .inputs import Policy, Region, Scenario, Vehicle
from .money import diesel_cost_per_mile, electric_cost_per_mile, money, present_value


@dataclass(frozen=True)
class CostLine:
    """One named component of cost, kept so the total can be explained."""

    label: str
    undiscounted: Decimal
    present_value: Decimal

    def __str__(self) -> str:
        return f"{self.label:<28} {self.present_value:>14,.0f}"


@dataclass(frozen=True)
class TCOResult:
    """The full picture for one vehicle in one region under one policy."""

    vehicle: str
    powertrain: str
    region: str
    policy: str
    years: int
    total_miles: Decimal
    lines: tuple[CostLine, ...]
    annual_cash_flow: tuple[Decimal, ...]
    cumulative_discounted: tuple[Decimal, ...] = field(default=())

    @property
    def total(self) -> Decimal:
        """Net present cost over the ownership period."""
        return sum((item.present_value for item in self.lines), Decimal(0))

    @property
    def cost_per_mile(self) -> Decimal:
        return self.total / self.total_miles if self.total_miles else Decimal(0)

    def line(self, label: str) -> CostLine | None:
        for item in self.lines:
            if item.label == label:
                return item
        return None


def _energy_cost_per_mile(v: Vehicle, r: Region, p: Policy) -> Decimal:
    """Fuel or electricity, per mile, including any per-gallon carbon tax."""
    if v.is_electric:
        return electric_cost_per_mile(r.electricity_price_per_kwh, v.kwh_per_mile)
    effective_price = money(r.diesel_price_per_gallon) + money(p.carbon_tax_per_gallon)
    return diesel_cost_per_mile(effective_price, v.miles_per_gallon)


def compute(v: Vehicle, r: Region, p: Policy, s: Scenario) -> TCOResult:
    """Net present cost of owning and running one vehicle for the period."""
    miles = money(s.annual_miles)
    total_miles = miles * s.years
    rate = money(s.discount_rate)

    # ---- year 0 capital ----
    capital = money(v.purchase_price)
    infra = money(v.charger_capital) if v.is_electric else Decimal(0)
    incentive = Decimal(0)
    if v.is_electric:
        incentive = (money(p.purchase_incentive) + money(p.charger_incentive)
                     + money(p.feebate_rebate_electric))
        # An incentive cannot exceed the capital it offsets. Without this cap an
        # over-generous lever shows the operator being paid to take the vehicle,
        # which is not a result any ministry would recognise.
        incentive = min(incentive, capital + infra)
    else:
        capital += money(p.feebate_on_diesel)

    # ---- annual operating flows ----
    energy_pm = _energy_cost_per_mile(v, r, p)
    energy_year = energy_pm * miles
    maint_year = money(v.maintenance_per_mile) * miles
    insurance_year = money(v.insurance_per_year)
    demand_year = money(r.demand_charge_per_year) if v.is_electric else Decimal(0)
    ruc_year = (money(p.road_user_charge_per_mile) * miles
                if v.powertrain in p.road_user_charge_applies_to else Decimal(0))

    def pv_annual(amount: Decimal) -> Decimal:
        return sum((present_value(amount, y, rate) for y in range(1, s.years + 1)), Decimal(0))

    residual = money(v.purchase_price) * money(v.residual_fraction)
    residual_pv = present_value(residual, s.years, rate)

    lines = (
        CostLine("Purchase price", capital, capital),
        CostLine("Charging infrastructure", infra, infra),
        CostLine("Incentives and rebates", -incentive, -incentive),
        CostLine("Energy", energy_year * s.years, pv_annual(energy_year)),
        CostLine("Maintenance", maint_year * s.years, pv_annual(maint_year)),
        CostLine("Insurance", insurance_year * s.years, pv_annual(insurance_year)),
        CostLine("Electricity demand charges", demand_year * s.years, pv_annual(demand_year)),
        CostLine("Road user charge", ruc_year * s.years, pv_annual(ruc_year)),
        CostLine("Residual value", -residual, -residual_pv),
    )

    annual = [capital + infra - incentive]
    for y in range(1, s.years + 1):
        flow = energy_year + maint_year + insurance_year + demand_year + ruc_year
        if y == s.years:
            flow -= residual
        annual.append(flow)

    cumulative, running = [], Decimal(0)
    for y, flow in enumerate(annual):
        running += present_value(flow, y, rate)
        cumulative.append(running)

    return TCOResult(
        vehicle=v.name, powertrain=v.powertrain, region=r.name, policy=p.name,
        years=s.years, total_miles=total_miles, lines=lines,
        annual_cash_flow=tuple(annual), cumulative_discounted=tuple(cumulative),
    )


@dataclass(frozen=True)
class Comparison:
    """Two vehicles under identical conditions, plus the crossover."""

    baseline: TCOResult
    alternative: TCOResult

    @property
    def difference(self) -> Decimal:
        """Positive means the alternative costs more over the full period."""
        return self.alternative.total - self.baseline.total

    @property
    def alternative_is_cheaper(self) -> bool:
        return self.difference < 0

    @property
    def breakeven_year(self) -> int | None:
        """First year in which the alternative's cumulative cost falls below.

        Returns None when it never does inside the ownership period, which is
        a real and common answer, and far more useful than extrapolating past
        the horizon the user asked about.
        """
        pairs = zip(self.baseline.cumulative_discounted,
                    self.alternative.cumulative_discounted, strict=False)
        for y, (a, b) in enumerate(pairs):
            if b <= a:
                return y
        return None

    @property
    def incremental_capital(self) -> Decimal:
        """Extra up-front cost of the alternative, after incentives."""
        return self.alternative.cumulative_discounted[0] - self.baseline.cumulative_discounted[0]
