"""Run the three shipped scenarios and print what the model concludes.

    python demo.py
"""

from pathlib import Path

from tcokit import (
    Comparison,
    compute,
    incentive_to_breakeven,
    load_scenario,
    render,
    tornado,
)

HERE = Path(__file__).parent


def main() -> None:
    for name in ("us_class8_baseline", "us_class8_incentivised", "colombia_corridor"):
        path = HERE / "scenarios" / f"{name}.yaml"
        diesel, electric, region, policy, scenario = load_scenario(path)
        c = Comparison(compute(diesel, region, policy, scenario),
                       compute(electric, region, policy, scenario))
        print("=" * 70)
        print(f"SCENARIO: {name}")
        print("=" * 70)
        print(render(c, tornado(diesel, electric, region, policy, scenario), region.currency))
        need = incentive_to_breakeven(diesel, electric, region, policy, scenario)
        if need is not None and not c.alternative_is_cheaper:
            print(f"\n  Smallest purchase incentive that would flip this: ${need:,.0f}")
        print()


if __name__ == "__main__":
    main()
