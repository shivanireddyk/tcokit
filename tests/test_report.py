import json
from pathlib import Path

from tcokit import Comparison, as_record, compute, load_scenario, render, tornado

SCEN = Path(__file__).resolve().parents[1] / "scenarios"


def _cmp(name):
    d, e, r, p, s = load_scenario(SCEN / f"{name}.yaml")
    return Comparison(compute(d, r, p, s), compute(e, r, p, s)), (d, e, r, p, s)


class TestRender:
    def test_leads_with_the_decision(self):
        c, _ = _cmp("us_class8_baseline")
        first = render(c).splitlines()[0]
        assert "over the period" in first
        assert first.startswith("Class 8 battery electric tractor is")

    def test_names_the_region_and_policy(self):
        c, _ = _cmp("us_class8_incentivised")
        text = render(c)
        assert "United States" in text and "voucher" in text.lower()

    def test_shows_component_lines_so_the_total_can_be_checked(self):
        c, _ = _cmp("us_class8_baseline")
        text = render(c)
        for label in ("Purchase price", "Energy", "Maintenance"):
            assert label in text

    def test_explains_a_missing_breakeven_rather_than_inventing_one(self):
        c, _ = _cmp("us_class8_baseline")
        if c.breakeven_year is None:
            assert "not within period" in render(c)
            assert "is a finding" in render(c)

    def test_sensitivity_section_appears_when_swings_are_supplied(self):
        c, (d, e, r, p, s) = _cmp("us_class8_incentivised")
        text = render(c, tornado(d, e, r, p, s))
        assert "Most influential assumptions" in text


class TestRecord:
    def test_is_json_serialisable(self):
        c, (d, e, r, p, s) = _cmp("us_class8_incentivised")
        json.dumps(as_record(c, tornado(d, e, r, p, s)))

    def test_captures_what_is_needed_to_reproduce_the_finding(self):
        c, _ = _cmp("us_class8_incentivised")
        rec = as_record(c)
        assert rec["region"] and rec["policy"] and rec["years"]
        assert "net_present_cost" in rec["baseline"]
        assert "cumulative_discounted" in rec["alternative"]
        assert isinstance(rec["alternative_is_cheaper"], bool)

    def test_money_is_recorded_as_strings_not_floats(self):
        c, _ = _cmp("us_class8_baseline")
        rec = as_record(c)
        assert isinstance(rec["difference"], str)
        assert all(isinstance(v, str) for v in rec["baseline"]["lines"].values())
