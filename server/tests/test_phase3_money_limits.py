from decimal import Decimal

import pytest

from app.modules.pricing.money import MAX_PAISE, price_line


def test_bigint_limit_rejected_before_database_write():
    with pytest.raises(ValueError, match="BIGINT"):
        price_line(
            unit_price_paise=MAX_PAISE,
            cost_unit_paise=0,
            quantity=Decimal("2.000"),
            discount_bps=0,
            gst_rate_bps=0,
            max_discount_bps=0,
            min_margin_bps=0,
        )
