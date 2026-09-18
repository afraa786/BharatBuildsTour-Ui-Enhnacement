from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.catalog.normalization import normalize_catalog_text
from app.modules.inventory.schemas import InventoryCheckIn


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        ("  SKU-001  ", "sku 001"),
        ("Copper   Wire", "copper wire"),
        ("Copper\tWire", "copper wire"),
        ("Copper\u00a0Wire", "copper wire"),
        ("Copper-Wire", "copper wire"),
        ("9w bulb", "9w bulb"),
    ],
)
def test_catalog_normalization_vectors(original: str, expected: str) -> None:
    assert normalize_catalog_text(original) == expected


@pytest.mark.parametrize("quantity", ["0.000", "-1.000", "1.1234", "NaN", "Infinity"])
def test_invalid_quantity_rejected(quantity: str) -> None:
    with pytest.raises(ValidationError):
        InventoryCheckIn(
            business_id=uuid4(), run_id="RFQ-test", product_id=uuid4(), requested_qty=quantity
        )


def test_valid_quantity_preserves_decimal_string() -> None:
    request = InventoryCheckIn(
        business_id=uuid4(), run_id="RFQ-test", product_id=uuid4(), requested_qty="1.500"
    )
    assert request.requested_qty == "1.500"
    assert Decimal(request.requested_qty) == Decimal("1.500")
