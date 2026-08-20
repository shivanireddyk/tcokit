from decimal import Decimal

import pytest

from tcokit.money import (
    UnitError,
    diesel_cost_per_mile,
    electric_cost_per_mile,
    money,
    present_value,
    to_cents,
)


class TestDecimalDiscipline:
    def test_float_is_rejected_at_the_boundary(self):
        with pytest.raises(TypeError, match="not float"):
            money(3.85)

    def test_strings_and_ints_are_accepted_exactly(self):
        assert money("3.85") == Decimal("3.85")
        assert money(150000) == Decimal("150000")

    def test_a_sum_float_would_get_wrong(self):
        # 0.1 + 0.2 != 0.3 in binary floating point. Over a ten year discounted
        # cash flow that error compounds, and it is the kind of discrepancy
        # nobody can explain later.
        assert money("0.1") + money("0.2") == money("0.3")

    def test_cents_rounding_is_half_up_and_display_only(self):
        assert to_cents(Decimal("1.005")) == Decimal("1.01")
        assert to_cents(Decimal("2.344")) == Decimal("2.34")


class TestTheReciprocalTrap:
    """Diesel divides by efficiency, electricity multiplies. Easy to invert."""

    def test_diesel_divides_price_by_mpg(self):
        # $3.85/gal at 6.5 mpg is about 59 cents a mile
        got = diesel_cost_per_mile(Decimal("3.85"), Decimal("6.5"))
        assert round(got, 4) == round(Decimal("3.85") / Decimal("6.5"), 4)
        assert Decimal("0.55") < got < Decimal("0.65")

    def test_electric_multiplies_price_by_consumption(self):
        # $0.16/kWh at 2.0 kWh/mile is 32 cents a mile
        assert electric_cost_per_mile(Decimal("0.16"), Decimal("2.0")) == Decimal("0.320")

    def test_inverting_electric_would_give_a_wrong_but_plausible_number(self):
        correct = electric_cost_per_mile(Decimal("0.16"), Decimal("2.0"))
        inverted = Decimal("0.16") / Decimal("2.0")
        assert correct != inverted
        assert correct == Decimal("0.32") and inverted == Decimal("0.08")

    def test_zero_or_negative_efficiency_raises(self):
        with pytest.raises(UnitError):
            diesel_cost_per_mile(Decimal("3.85"), Decimal("0"))
        with pytest.raises(UnitError):
            electric_cost_per_mile(Decimal("0.16"), Decimal("-1"))


class TestDiscounting:
    def test_year_zero_is_undiscounted(self):
        assert present_value(Decimal("1000"), 0, Decimal("0.07")) == Decimal("1000")

    def test_a_future_cost_is_worth_less_now(self):
        assert present_value(Decimal("1000"), 5, Decimal("0.07")) < Decimal("1000")

    def test_matches_the_textbook_formula(self):
        got = present_value(Decimal("1000"), 3, Decimal("0.10"))
        assert round(got, 2) == round(Decimal("1000") / (Decimal("1.10") ** 3), 2)

    def test_zero_rate_leaves_value_unchanged(self):
        assert present_value(Decimal("1000"), 9, Decimal("0")) == Decimal("1000")

    def test_negative_year_raises(self):
        with pytest.raises(ValueError):
            present_value(Decimal("1000"), -1, Decimal("0.07"))
