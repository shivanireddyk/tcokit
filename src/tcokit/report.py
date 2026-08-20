"""Turn a comparison into something a non-modeller can read and act on.

The audience for this output is a policy analyst or a fleet manager, not the
person who wrote the model. So the report leads with the decision, shows the
components that produced it, and names the assumption the answer is most
sensitive to, because that is the first thing a sceptical reader will ask.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from .sensitivity import Swing
from .tco import Comparison, TCOResult


def _fmt(x: Decimal, currency: str = "USD") -> str:
    sign = "-" if x < 0 else ""
    symbol = "$" if currency == "USD" else ""
    return f"{sign}{symbol}{abs(x):,.0f}"


def render_vehicle(r: TCOResult, currency: str = "USD") -> str:
    lines = [f"{r.vehicle}  ({r.powertrain}, {r.years} years, {r.total_miles:,.0f} miles)"]
    lines.append("-" * 46)
    for item in r.lines:
        if item.present_value == 0:
            continue
        lines.append(f"  {item.label:<28}{_fmt(item.present_value, currency):>16}")
    lines.append("-" * 46)
    lines.append(f"  {'Net present cost':<28}{_fmt(r.total, currency):>16}")
    lines.append(f"  {'Cost per mile':<28}{r.cost_per_mile:>15.3f}")
    return "\n".join(lines)


def render(c: Comparison, swings: list[Swing] | None = None, currency: str = "USD") -> str:
    """The full comparison, decision first."""
    a, b = c.baseline, c.alternative
    verdict = ("CHEAPER over the period" if c.alternative_is_cheaper
               else "MORE EXPENSIVE over the period")
    out = [
        f"{b.vehicle} is {verdict} than {a.vehicle}",
        f"Region: {a.region}    Policy: {a.policy}",
        "=" * 46,
        "",
        render_vehicle(a, currency),
        "",
        render_vehicle(b, currency),
        "",
        "-" * 46,
        f"  {'Difference':<28}{_fmt(c.difference, currency):>16}",
        f"  {'Extra up-front cost':<28}{_fmt(c.incremental_capital, currency):>16}",
    ]
    be = c.breakeven_year
    shown = f"year {be}" if be is not None else "not within period"
    out.append(f"  {'Breakeven':<28}{shown:>16}")
    if be is None:
        out.append("")
        out.append("  The electric vehicle does not become cheaper inside the ownership")
        out.append("  period under these assumptions. That is a finding, not a failure of")
        out.append("  the model: it is the number a policy lever would have to move.")
    if swings:
        out += ["", "Most influential assumptions", "-" * 46]
        for s in swings[:5]:
            flag = "  <- changes the decision" if s.changes_the_decision else ""
            out.append(f"  {s.input_name:<28}{_fmt(s.swing, currency):>16}{flag}")
    return "\n".join(out)


def as_record(c: Comparison, swings: list[Swing] | None = None) -> dict[str, Any]:
    """Serialisable record, so a run can be stored, diffed or charted."""
    def veh(r: TCOResult) -> dict[str, Any]:
        return {
            "vehicle": r.vehicle, "powertrain": r.powertrain,
            "net_present_cost": str(r.total), "cost_per_mile": str(round(r.cost_per_mile, 4)),
            "lines": {item.label: str(item.present_value)
                      for item in r.lines if item.present_value != 0},
            "cumulative_discounted": [str(x) for x in r.cumulative_discounted],
        }
    rec = {
        "region": c.baseline.region, "policy": c.baseline.policy,
        "years": c.baseline.years, "total_miles": str(c.baseline.total_miles),
        "baseline": veh(c.baseline), "alternative": veh(c.alternative),
        "difference": str(c.difference),
        "alternative_is_cheaper": c.alternative_is_cheaper,
        "breakeven_year": c.breakeven_year,
        "incremental_capital": str(c.incremental_capital),
    }
    if swings:
        rec["sensitivity"] = [
            {"input": s.input_name, "swing": str(s.swing),
             "changes_the_decision": s.changes_the_decision} for s in swings
        ]
    return rec
