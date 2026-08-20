from decimal import Decimal
from pathlib import Path

import pytest

from tcokit import load_scenario
from tcokit.inputs import (
    InputError,
    policy_from_dict,
    region_from_dict,
    scenario_from_dict,
    vehicle_from_dict,
)

SCEN = Path(__file__).resolve().parents[1] / "scenarios"

GOOD_DIESEL = {"name": "D", "powertrain": "diesel", "purchase_price": "150000",
               "miles_per_gallon": "6.5"}
GOOD_ELEC = {"name": "E", "powertrain": "electric", "purchase_price": "350000",
             "kwh_per_mile": "2.0"}


class TestShippedScenariosAreValid:
    @pytest.mark.parametrize("name", ["us_class8_baseline", "us_class8_incentivised",
                                      "colombia_corridor"])
    def test_every_shipped_scenario_loads(self, name):
        d, e, r, p, s = load_scenario(SCEN / f"{name}.yaml")
        assert d.powertrain == "diesel" and e.powertrain == "electric"
        assert r.name and s.years >= 1

    def test_the_two_us_scenarios_differ_only_in_policy(self):
        d1, e1, r1, p1, s1 = load_scenario(SCEN / "us_class8_baseline.yaml")
        d2, e2, r2, p2, s2 = load_scenario(SCEN / "us_class8_incentivised.yaml")
        assert (d1, e1, r1, s1) == (d2, e2, r2, s2)
        assert p1 != p2


class TestValidationRefusesBadInput:
    def test_float_in_yaml_is_rejected(self):
        with pytest.raises(InputError, match="not 3.85"):
            vehicle_from_dict({**GOOD_DIESEL, "purchase_price": 3.85})

    def test_unknown_powertrain_is_rejected(self):
        with pytest.raises(InputError, match="powertrain"):
            vehicle_from_dict({**GOOD_DIESEL, "powertrain": "hydrogen"})

    def test_diesel_without_mpg_is_rejected(self):
        d = {k: v for k, v in GOOD_DIESEL.items() if k != "miles_per_gallon"}
        with pytest.raises(KeyError):
            vehicle_from_dict(d)

    def test_diesel_carrying_kwh_is_rejected_rather_than_ignored(self):
        with pytest.raises(InputError, match="must not define kwh_per_mile"):
            vehicle_from_dict({**GOOD_DIESEL, "kwh_per_mile": "2.0"})

    def test_electric_carrying_mpg_is_rejected(self):
        with pytest.raises(InputError, match="must not define miles_per_gallon"):
            vehicle_from_dict({**GOOD_ELEC, "miles_per_gallon": "6.5"})

    def test_residual_fraction_outside_zero_to_one_is_rejected(self):
        with pytest.raises(InputError, match="between 0 and 1"):
            vehicle_from_dict({**GOOD_DIESEL, "residual_fraction": "1.4"})

    def test_zero_or_negative_years_is_rejected(self):
        with pytest.raises(InputError, match="positive integer"):
            scenario_from_dict({"years": 0})

    def test_bad_road_charge_target_is_rejected(self):
        with pytest.raises(InputError, match="road_user_charge_applies_to"):
            policy_from_dict({"road_user_charge_applies_to": ["hovercraft"]})

    def test_missing_file_raises_input_error_not_oserror(self):
        with pytest.raises(InputError, match="cannot read"):
            load_scenario("/nonexistent/scenario.yaml")

    def test_missing_section_is_named(self, tmp_path):
        f = tmp_path / "partial.yaml"
        f.write_text("region:\n  name: Nowhere\n", encoding="utf-8")
        with pytest.raises(InputError, match="baseline_vehicle"):
            load_scenario(f)


class TestDefaults:
    def test_policy_defaults_to_no_levers(self):
        p = policy_from_dict({})
        assert p.purchase_incentive == Decimal("0")
        assert p.carbon_tax_per_gallon == Decimal("0")

    def test_region_defaults_to_usd(self):
        assert region_from_dict({"name": "X"}).currency == "USD"
