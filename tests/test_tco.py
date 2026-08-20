"""The tests that decide whether the number can be trusted.

Each one exists because getting it wrong produces a confident, plausible
figure that a policy analyst would act on.
"""

from dataclasses import replace
from decimal import Decimal
from pathlib import Path

import pytest

from tcokit import Comparison, compute, load_scenario
from tcokit.inputs import Policy, Region, Scenario, Vehicle
from tcokit.money import to_cents

SCEN = Path(__file__).resolve().parents[1] / "scenarios"

DIESEL = Vehicle(name="D", powertrain="diesel", purchase_price=Decimal("150000"),
                 miles_per_gallon=Decimal("6.5"), maintenance_per_mile=Decimal("0.19"))
ELECTRIC = Vehicle(name="E", powertrain="electric", purchase_price=Decimal("350000"),
                   kwh_per_mile=Decimal("2.0"), maintenance_per_mile=Decimal("0.11"),
                   charger_capital=Decimal("120000"))
REGION = Region(name="R", diesel_price_per_gallon=Decimal("3.85"),
                electricity_price_per_kwh=Decimal("0.16"))
NONE = Policy()
S = Scenario(years=10, annual_miles=Decimal("80000"), discount_rate=Decimal("0.07"))


class TestArithmeticBasics:
    def test_total_is_the_sum_of_its_lines(self):
        r = compute(DIESEL, REGION, NONE, S)
        assert r.total == sum(item.present_value for item in r.lines)

    def test_cost_per_mile_is_total_over_miles(self):
        r = compute(DIESEL, REGION, NONE, S)
        assert r.cost_per_mile == r.total / (Decimal("80000") * 10)

    def test_zero_discount_makes_present_value_equal_undiscounted(self):
        # At a zero discount rate the two figures are the same quantity reached
        # two ways: one multiplication, and ten divisions summed. Decimal keeps
        # 28 significant digits, so those agree to about 1e-22 of a dollar
        # rather than bit for bit. Asserting equality to the cent is the honest
        # claim, and it is the precision anyone actually relies on.
        r = compute(DIESEL, REGION, NONE, replace(S, discount_rate=Decimal("0")))
        energy = r.line("Energy")
        assert to_cents(energy.present_value) == to_cents(energy.undiscounted)

    def test_discounting_reduces_the_value_of_future_costs(self):
        flat = compute(DIESEL, REGION, NONE, replace(S, discount_rate=Decimal("0")))
        disc = compute(DIESEL, REGION, NONE, replace(S, discount_rate=Decimal("0.10")))
        assert disc.line("Energy").present_value < flat.line("Energy").present_value

    def test_residual_value_is_a_credit_not_a_cost(self):
        with_resid = compute(replace(DIESEL, residual_fraction=Decimal("0.25")), REGION, NONE, S)
        assert with_resid.line("Residual value").present_value < 0

    def test_longer_ownership_costs_more_in_total(self):
        short = compute(DIESEL, REGION, NONE, replace(S, years=5))
        long = compute(DIESEL, REGION, NONE, replace(S, years=15))
        assert long.total > short.total


class TestPowertrainsAreTreatedDifferently:
    def test_diesel_pays_no_demand_charge(self):
        r = Region(name="R", diesel_price_per_gallon=Decimal("3.85"),
                   electricity_price_per_kwh=Decimal("0.16"),
                   demand_charge_per_year=Decimal("9000"))
        assert compute(DIESEL, r, NONE, S).line("Electricity demand charges").present_value == 0
        assert compute(ELECTRIC, r, NONE, S).line("Electricity demand charges").present_value > 0

    def test_only_electric_pays_charger_capital(self):
        assert compute(DIESEL, REGION, NONE, S).line("Charging infrastructure").present_value == 0
        electric = compute(ELECTRIC, REGION, NONE, S)
        assert electric.line("Charging infrastructure").present_value == Decimal("120000")

    def test_carbon_tax_hits_diesel_only(self):
        taxed = Policy(name="carbon", carbon_tax_per_gallon=Decimal("1.00"))
        d0 = compute(DIESEL, REGION, NONE, S).line("Energy").present_value
        d1 = compute(DIESEL, REGION, taxed, S).line("Energy").present_value
        e0 = compute(ELECTRIC, REGION, NONE, S).line("Energy").present_value
        e1 = compute(ELECTRIC, REGION, taxed, S).line("Energy").present_value
        assert d1 > d0
        assert e1 == e0


class TestPolicyLevers:
    def test_purchase_incentive_reduces_electric_cost(self):
        p = Policy(name="voucher", purchase_incentive=Decimal("100000"))
        assert compute(ELECTRIC, REGION, p, S).total < compute(ELECTRIC, REGION, NONE, S).total

    def test_an_incentive_cannot_exceed_the_capital_it_offsets(self):
        # A cap matters: without it, an over-generous lever would show the
        # operator being paid to accept the vehicle, which is not a real result.
        huge = Policy(name="absurd", purchase_incentive=Decimal("9000000"))
        r = compute(ELECTRIC, REGION, huge, S)
        capital = (r.line("Purchase price").present_value
                   + r.line("Charging infrastructure").present_value)
        assert abs(r.line("Incentives and rebates").present_value) <= capital

    def test_feebate_charges_diesel_and_rebates_electric(self):
        fb = Policy(name="feebate", feebate_on_diesel=Decimal("10000"),
                    feebate_rebate_electric=Decimal("10000"))
        assert compute(DIESEL, REGION, fb, S).total > compute(DIESEL, REGION, NONE, S).total
        assert compute(ELECTRIC, REGION, fb, S).total < compute(ELECTRIC, REGION, NONE, S).total

    def test_road_charge_can_target_one_powertrain(self):
        only_diesel = Policy(name="ruc", road_user_charge_per_mile=Decimal("0.05"),
                             road_user_charge_applies_to=("diesel",))
        assert compute(DIESEL, REGION, only_diesel, S).line("Road user charge").present_value > 0
        assert compute(ELECTRIC, REGION, only_diesel, S).line("Road user charge").present_value == 0

    def test_no_policy_changes_nothing(self):
        a = compute(ELECTRIC, REGION, Policy(), S).total
        b = compute(ELECTRIC, REGION, Policy(name="x"), S).total
        assert a == b


class TestComparison:
    def test_electric_loses_on_capital_alone_without_support(self):
        c = Comparison(compute(DIESEL, REGION, NONE, S), compute(ELECTRIC, REGION, NONE, S))
        assert c.incremental_capital > 0

    def test_a_large_enough_incentive_flips_the_decision(self):
        rich = Policy(name="rich", purchase_incentive=Decimal("250000"),
                      charger_incentive=Decimal("120000"))
        c = Comparison(compute(DIESEL, REGION, rich, S), compute(ELECTRIC, REGION, rich, S))
        assert c.alternative_is_cheaper

    def test_breakeven_is_none_when_it_never_crosses(self):
        # This is a real answer, not a failure. A model that invented a year
        # here would be extrapolating past the horizon it was asked about.
        c = Comparison(compute(DIESEL, REGION, NONE, replace(S, years=3)),
                       compute(ELECTRIC, REGION, NONE, replace(S, years=3)))
        assert c.breakeven_year is None

    def test_breakeven_year_is_within_the_period_when_it_crosses(self):
        rich = Policy(name="rich", purchase_incentive=Decimal("250000"),
                      charger_incentive=Decimal("120000"))
        c = Comparison(compute(DIESEL, REGION, rich, S), compute(ELECTRIC, REGION, rich, S))
        assert c.breakeven_year is not None
        assert 0 <= c.breakeven_year <= S.years

    def test_difference_sign_matches_the_verdict(self):
        c = Comparison(compute(DIESEL, REGION, NONE, S), compute(ELECTRIC, REGION, NONE, S))
        assert (c.difference < 0) == c.alternative_is_cheaper


class TestShippedScenariosRun:
    @pytest.mark.parametrize("name", ["us_class8_baseline", "us_class8_incentivised",
                                      "colombia_corridor"])
    def test_every_scenario_produces_a_finite_comparison(self, name):
        d, e, r, p, s = load_scenario(SCEN / f"{name}.yaml")
        c = Comparison(compute(d, r, p, s), compute(e, r, p, s))
        assert c.baseline.total > 0 and c.alternative.total != 0
        assert len(c.baseline.cumulative_discounted) == s.years + 1

    def test_policy_support_narrows_the_gap_on_identical_inputs(self):
        d1, e1, r1, p1, s1 = load_scenario(SCEN / "us_class8_baseline.yaml")
        d2, e2, r2, p2, s2 = load_scenario(SCEN / "us_class8_incentivised.yaml")
        plain = Comparison(compute(d1, r1, p1, s1), compute(e1, r1, p1, s1)).difference
        supported = Comparison(compute(d2, r2, p2, s2), compute(e2, r2, p2, s2)).difference
        assert supported < plain
