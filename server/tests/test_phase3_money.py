from decimal import Decimal

import pytest

from app.modules.pricing.money import price_line


def _price(**overrides):
    values = {
        "unit_price_paise": 1000,
        "cost_unit_paise": 500,
        "quantity": Decimal("1.000"),
        "discount_bps": 0,
        "gst_rate_bps": 1800,
        "max_discount_bps": 1000,
        "min_margin_bps": 2000,
    }
    values.update(overrides)
    return price_line(**values)


def test_no_discount_and_fractional_half_up():
    assert _price().line_total_paise == 1180
    line = _price(
        unit_price_paise=1500,
        cost_unit_paise=500,
        quantity=Decimal("1.500"),
        discount_bps=501,
    )
    assert (line.gross_paise, line.discount_paise, line.taxable_paise) == (2250, 113, 2137)
    assert (line.tax_paise, line.line_total_paise) == (385, 2522)


def test_6413_tax_and_quote_line_rounding_boundary():
    line = _price(
        unit_price_paise=15000,
        cost_unit_paise=10000,
        quantity=Decimal("2.500"),
        discount_bps=500,
    )
    assert line.taxable_paise == 35625
    assert line.tax_paise == 6413
    pennies = [_price(unit_price_paise=10, cost_unit_paise=0, min_margin_bps=0) for _ in range(3)]
    assert sum(item.tax_paise for item in pennies) == 6
    assert sum(item.line_total_paise for item in pennies) == 36


def test_discount_cap_and_margin_floor_are_independent():
    cap = _price(
        unit_price_paise=100000,
        cost_unit_paise=10000,
        discount_bps=1501,
    )
    assert cap.discount_paise == 15010  # requested 1501 bps, not clipped to 1000 bps
    assert cap.approval_reasons == ("DISCOUNT_EXCEEDS_CAP",)
    exact = _price(gst_rate_bps=0, cost_unit_paise=800, min_margin_bps=2000)
    assert exact.approval_reasons == ()
    below = _price(gst_rate_bps=0, cost_unit_paise=801, min_margin_bps=2000)
    assert below.approval_reasons == ("MARGIN_BELOW_FLOOR",)


def test_zero_revenue_is_invalid_not_approvable():
    with pytest.raises(ValueError, match="taxable revenue"):
        _price(discount_bps=10000, max_discount_bps=10000)


def test_invalid_paise_and_basis_points():
    with pytest.raises(ValueError):
        _price(unit_price_paise=0)
    with pytest.raises(ValueError):
        _price(discount_bps=10001)
