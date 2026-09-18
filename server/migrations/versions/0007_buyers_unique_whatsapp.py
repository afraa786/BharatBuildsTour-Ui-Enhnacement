"""Add unique constraint for buyer business_id and whatsapp

Revision ID: 0006_buyers_unique_whatsapp
Revises: 0005_buyers_boolean_customer
"""

from collections.abc import Sequence

from alembic import op

revision = "0007_buyers_unique_whatsapp"
down_revision: str | Sequence[str] | None = "0006_whatsapp_routing_bindings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop the plain index before adding the unique constraint (it provides an index).
    op.drop_index("ix_buyers_business_whatsapp", table_name="buyers")
    op.create_unique_constraint(
        "uq_buyers_business_id_whatsapp", "buyers", ["business_id", "whatsapp_e164"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_buyers_business_id_whatsapp", "buyers", type_="unique")
    op.create_index(
        "ix_buyers_business_whatsapp", "buyers", ["business_id", "whatsapp_e164"], unique=False
    )
