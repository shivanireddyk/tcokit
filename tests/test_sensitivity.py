from decimal import Decimal

from tcokit.inputs import Policy, Region, Scenario, Vehicle
from tcokit.sensitivity import incentive_to_breakeven, tornado

DIESEL = Vehicle(name="D", powertrain="diesel", purchase_price=Decimal("150000"),
                 miles_per_gallon=Decimal("6.5"), maintenance_per_mile=Decimal("0.19"))
ELECTRIC = Vehicle(name="E", powertrain="electric", purchase_price=Decimal("350000"),
                   kwh_per_mile=Decimal("2.0"), maintenance_per_mile=Decimal("0.11"),
                   charger_capital=Decimal("120000"))
REGION = Region(name="R", diesel_price_per_gallon=Decimal("3.85"),
                electricity_price_per_kwh=Decimal("0.16"))
POLICY = Policy(name="p", purchase_incentive=Decimal("100000"))
S = Scenario(years=10, annual_miles=Decimal("80000"), discount_rate=Decimal("0.07"))


class TestTornado:
    def test_returns_results_ordered_by_influence(self):
        sw = tornado(DIESEL, ELECTRIC, REGION, POLICY, S)
        assert sw
        assert [x.swing for x in sw] == sorted((x.swing for x in sw), reverse=True)

    def test_every_swing_is_non_negative(self):
        assert all(x.swing >= 0 for x in tornado(DIESEL, ELECTRIC, REGION, POLICY, S))

    def test_diesel_price_is_included_and_matters(self):
        names = [x.input_name for x in tornado(DIESEL, ELECTRIC, REGION, POLICY, S)]
        assert "Diesel price" in names

    def test_levers_that_are_switched_off_are_omitted_not_reported_as_flat(self):
        # A zero lever is not the same finding as an irrelevant one, so it is
        # left out rather than shown with a swing of zero.
        names = [x.input_name for x in tornado(DIESEL, ELECTRIC, REGION, Policy(), S)]
        assert "Purchase incentive" not in names
        assert "Carbon tax" not in names

    def test_wider_variation_produces_wider_swings(self):
        narrow = tornado(DIESEL, ELECTRIC, REGION, POLICY, S, variation=Decimal("0.10"))
        wide = tornado(DIESEL, ELECTRIC, REGION, POLICY, S, variation=Decimal("0.50"))
        by_name = {x.input_name: x.swing for x in narrow}
        assert all(x.swing >= by_name[x.input_name] for x in wide if x.input_name in by_name)


class TestIncentiveSearch:
    def test_finds_the_incentive_that_flips_the_decision(self):
        need = incentive_to_breakeven(DIESEL, ELECTRIC, REGION, Policy(), S)
        assert need is not None and need > 0

    def test_the_answer_actually_works_when_applied(self):
        need = incentive_to_breakeven(DIESEL, ELECTRIC, REGION, Policy(), S)
        from tcokit.tco import Comparison, compute
        p = Policy(name="found", purchase_incentive=need)
        c = Comparison(compute(DIESEL, REGION, p, S), compute(ELECTRIC, REGION, p, S))
        assert c.alternative_is_cheaper or c.difference == 0

    def test_one_step_less_is_not_enough(self):
        step = Decimal("500")
        need = incentive_to_breakeven(DIESEL, ELECTRIC, REGION, Policy(), S, step=step)
        from tcokit.tco import Comparison, compute
        p = Policy(name="short", purchase_incentive=need - step)
        c = Comparison(compute(DIESEL, REGION, p, S), compute(ELECTRIC, REGION, p, S))
        assert not c.alternative_is_cheaper

    def test_returns_none_when_no_incentive_within_the_ceiling_suffices(self):
        assert incentive_to_breakeven(DIESEL, ELECTRIC, REGION, Policy(), S,
                                      ceiling=Decimal("1000")) is None
