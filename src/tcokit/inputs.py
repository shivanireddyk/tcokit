"""Vehicles, regions and policies, all held as editable data.

The reason this library exists in this shape is the phrase "prepare existing
tools and resources for global adaptation and replication". A model whose fuel
prices and incentives are written into Python only ever answers the question it
was built for. Moving those to YAML means the same engine answers the question
for California, for Colombia and for Poland, and the person changing the
numbers does not have to be the person who wrote the code.

So there are three data objects and no hardcoded figures anywhere:

    Vehicle   what you are buying and how it consumes energy
    Region    where you are operating it and what energy costs there
    Policy    what the government is doing about it

Every one is validated on load. A scenario file with a missing field or an
impossible value fails immediately rather than producing a confident number.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import yaml

from .money import money


class InputError(ValueError):
    """A scenario file is not usable. Never defaulted around."""


DIESEL = "diesel"
ELECTRIC = "electric"
_POWERTRAINS = (DIESEL, ELECTRIC)


@dataclass(frozen=True)
class Vehicle:
    """One vehicle configuration.

    Efficiency is deliberately powertrain-specific rather than a single
    "efficiency" field, because miles per gallon and kilowatt hours per mile
    are reciprocal and storing them in one field invites the inversion this
    library is careful about.
    """

    name: str
    powertrain: str
    purchase_price: Decimal
    miles_per_gallon: Decimal | None = None
    kwh_per_mile: Decimal | None = None
    maintenance_per_mile: Decimal = Decimal("0")
    insurance_per_year: Decimal = Decimal("0")
    residual_fraction: Decimal = Decimal("0")
    charger_capital: Decimal = Decimal("0")

    @property
    def is_electric(self) -> bool:
        return self.powertrain == ELECTRIC


@dataclass(frozen=True)
class Region:
    """Where the vehicle operates, and what energy costs there."""

    name: str
    currency: str = "USD"
    diesel_price_per_gallon: Decimal = Decimal("0")
    electricity_price_per_kwh: Decimal = Decimal("0")
    demand_charge_per_year: Decimal = Decimal("0")


@dataclass(frozen=True)
class Policy:
    """The levers a government can actually pull.

    These are the five named in CALSTART's own framing of the problem, and
    each one is applied at a different point in the cash flow, which is why
    they cannot be collapsed into a single subsidy number:

      purchase_incentive   reduces capital in year 0
      charger_incentive    reduces infrastructure capital in year 0
      road_user_charge     per mile, every year, on the named powertrains
      feebate              a fee on diesel purchase funding a rebate on electric
      carbon_tax           per gallon of diesel burned, every year
    """

    name: str = "none"
    purchase_incentive: Decimal = Decimal("0")
    charger_incentive: Decimal = Decimal("0")
    road_user_charge_per_mile: Decimal = Decimal("0")
    road_user_charge_applies_to: tuple[str, ...] = _POWERTRAINS
    feebate_on_diesel: Decimal = Decimal("0")
    feebate_rebate_electric: Decimal = Decimal("0")
    carbon_tax_per_gallon: Decimal = Decimal("0")


@dataclass(frozen=True)
class Scenario:
    """Everything that is not the vehicle: how long, how far, how discounted."""

    years: int = 10
    annual_miles: Decimal = Decimal("60000")
    discount_rate: Decimal = Decimal("0.05")


def _decimal(raw: Any, where: str) -> Decimal:
    if raw is None:
        raise InputError(f"{where} is required")
    if isinstance(raw, float):
        raise InputError(
            f'{where}: write numbers as strings, e.g. "3.85", not 3.85. '
            f"Floats are not exact and this is a money model."
        )
    try:
        return money(raw)
    except (InvalidOperation, TypeError):
        raise InputError(f"{where}: {raw!r} is not a number") from None


def vehicle_from_dict(d: dict[str, Any]) -> Vehicle:
    name = d.get("name")
    if not name:
        raise InputError("vehicle: 'name' is required")
    pt = d.get("powertrain")
    if pt not in _POWERTRAINS:
        raise InputError(f"vehicle {name}: 'powertrain' must be one of {_POWERTRAINS}, got {pt!r}")

    mpg = kwh = None
    if pt == DIESEL:
        mpg = _decimal(d["miles_per_gallon"], f"vehicle {name}: miles_per_gallon")
    else:
        kwh = _decimal(d["kwh_per_mile"], f"vehicle {name}: kwh_per_mile")
    if pt == DIESEL and "kwh_per_mile" in d:
        raise InputError(f"vehicle {name}: a diesel vehicle must not define kwh_per_mile")
    if pt == ELECTRIC and "miles_per_gallon" in d:
        raise InputError(f"vehicle {name}: an electric vehicle must not define miles_per_gallon")

    residual = _decimal(d.get("residual_fraction", "0"), f"vehicle {name}: residual_fraction")
    if not (Decimal(0) <= residual <= Decimal(1)):
        raise InputError(
            f"vehicle {name}: residual_fraction must be between 0 and 1, got {residual}"
        )

    return Vehicle(
        name=name,
        powertrain=pt,
        purchase_price=_decimal(d.get("purchase_price"), f"vehicle {name}: purchase_price"),
        miles_per_gallon=mpg,
        kwh_per_mile=kwh,
        maintenance_per_mile=_decimal(
            d.get("maintenance_per_mile", "0"), f"vehicle {name}: maintenance_per_mile"),
        insurance_per_year=_decimal(
            d.get("insurance_per_year", "0"), f"vehicle {name}: insurance_per_year"),
        residual_fraction=residual,
        charger_capital=_decimal(
            d.get("charger_capital", "0"), f"vehicle {name}: charger_capital"),
    )


def region_from_dict(d: dict[str, Any]) -> Region:
    name = d.get("name")
    if not name:
        raise InputError("region: 'name' is required")
    return Region(
        name=name,
        currency=str(d.get("currency", "USD")),
        diesel_price_per_gallon=_decimal(
            d.get("diesel_price_per_gallon", "0"), f"region {name}: diesel_price_per_gallon"),
        electricity_price_per_kwh=_decimal(
            d.get("electricity_price_per_kwh", "0"), f"region {name}: electricity_price_per_kwh"),
        demand_charge_per_year=_decimal(
            d.get("demand_charge_per_year", "0"), f"region {name}: demand_charge_per_year"),
    )


def policy_from_dict(d: dict[str, Any]) -> Policy:
    applies = d.get("road_user_charge_applies_to", list(_POWERTRAINS))
    if not isinstance(applies, list) or any(a not in _POWERTRAINS for a in applies):
        raise InputError(
            f"policy: road_user_charge_applies_to must be a list drawn from {_POWERTRAINS}"
        )
    return Policy(
        name=str(d.get("name", "unnamed")),
        purchase_incentive=_decimal(
            d.get("purchase_incentive", "0"), "policy: purchase_incentive"),
        charger_incentive=_decimal(
            d.get("charger_incentive", "0"), "policy: charger_incentive"),
        road_user_charge_per_mile=_decimal(
            d.get("road_user_charge_per_mile", "0"), "policy: road_user_charge_per_mile"),
        road_user_charge_applies_to=tuple(applies),
        feebate_on_diesel=_decimal(
            d.get("feebate_on_diesel", "0"), "policy: feebate_on_diesel"),
        feebate_rebate_electric=_decimal(
            d.get("feebate_rebate_electric", "0"), "policy: feebate_rebate_electric"),
        carbon_tax_per_gallon=_decimal(
            d.get("carbon_tax_per_gallon", "0"), "policy: carbon_tax_per_gallon"),
    )


def scenario_from_dict(d: dict[str, Any]) -> Scenario:
    years = d.get("years", 10)
    if not isinstance(years, int) or years < 1:
        raise InputError(f"scenario: 'years' must be a positive integer, got {years!r}")
    return Scenario(
        years=years,
        annual_miles=_decimal(d.get("annual_miles", "60000"), "scenario: annual_miles"),
        discount_rate=_decimal(
            d.get("discount_rate", "0.05"), "scenario: discount_rate"),
    )


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Read a YAML file, raising InputError rather than leaking OSError."""
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise InputError(f"cannot read {p}: {exc}") from None
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise InputError(f"{p} is not valid YAML: {exc}") from None
    if not isinstance(data, dict):
        raise InputError(f"{p} must contain a YAML mapping at the top level")
    return data
