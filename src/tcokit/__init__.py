"""tcokit: total cost of ownership for medium and heavy duty vehicles.

    from tcokit import load_scenario, compute, Comparison, render, tornado

    diesel, electric, region, policy, scenario = load_scenario("scenarios/us_baseline.yaml")
    c = Comparison(compute(diesel, region, policy, scenario),
                   compute(electric, region, policy, scenario))
    print(render(c, tornado(diesel, electric, region, policy, scenario)))

Built around one idea: the fuel prices, incentives and vehicle figures live in
YAML, not in Python, so the same engine answers the question for California,
Colombia or Poland by pointing it at a different file.
"""

from .inputs import (
    DIESEL,
    ELECTRIC,
    InputError,
    Policy,
    Region,
    Scenario,
    Vehicle,
    load_yaml,
    policy_from_dict,
    region_from_dict,
    scenario_from_dict,
    vehicle_from_dict,
)
from .money import (
    UnitError,
    diesel_cost_per_mile,
    electric_cost_per_mile,
    money,
    present_value,
    to_cents,
)
from .report import as_record, render, render_vehicle
from .sensitivity import Swing, incentive_to_breakeven, tornado
from .tco import Comparison, CostLine, TCOResult, compute

__version__ = "0.1.0"


def load_scenario(path):
    """Load a complete scenario file into its five objects."""
    d = load_yaml(path)
    for key in ("baseline_vehicle", "alternative_vehicle", "region"):
        if key not in d:
            raise InputError(f"{path}: missing required section '{key}'")
    return (
        vehicle_from_dict(d["baseline_vehicle"]),
        vehicle_from_dict(d["alternative_vehicle"]),
        region_from_dict(d["region"]),
        policy_from_dict(d.get("policy", {})),
        scenario_from_dict(d.get("scenario", {})),
    )


__all__ = [
    "Comparison", "CostLine", "DIESEL", "ELECTRIC", "InputError", "Policy",
    "Region", "Scenario", "Swing", "TCOResult", "UnitError", "Vehicle",
    "as_record", "compute", "diesel_cost_per_mile", "electric_cost_per_mile",
    "incentive_to_breakeven", "load_scenario", "load_yaml", "money",
    "policy_from_dict", "present_value", "region_from_dict", "render",
    "render_vehicle", "scenario_from_dict", "to_cents", "tornado",
    "vehicle_from_dict",
]
