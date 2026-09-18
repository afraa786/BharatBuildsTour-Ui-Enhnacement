"""Owner dashboard run lookups must survive both identifier shapes.

`runs.quote_id`/`payment_id`/`invoice_id` are string columns, and two writers
disagree about what goes in them: the WhatsApp flow stores display labels
("Q-1006-V1", "pay_1006", "INV-1006") while the owner seed stores real row UUIDs.
Comparing a label against a UUID primary key made PostgreSQL raise a DataError,
which surfaced as a 500 -- and the browser rendered that as "Failed to fetch".
"""

from uuid import UUID

from app.api.owner_routes import _row_id

SEEDED_UUID = "32ec7362-f654-5634-9196-a5248f01d3e8"


def test_display_labels_are_not_treated_as_row_ids() -> None:
    assert _row_id("Q-1006-V1") is None
    assert _row_id("pay_1006") is None
    assert _row_id("INV-1006") is None
    assert _row_id("") is None
    assert _row_id(None) is None


def test_real_row_ids_are_preserved() -> None:
    assert _row_id(SEEDED_UUID) == UUID(SEEDED_UUID)
    assert _row_id(SEEDED_UUID.upper()) == UUID(SEEDED_UUID)
