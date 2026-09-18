"""Replace buyers.type (lead/customer string) with buyers.is_customer boolean.

Revision ID: 0005_buyers_boolean_customer
Revises: 0004_owner_dashboard

This migration was already applied directly against the shared dev
database outside of this repo's history (the live schema already has
`is_customer` and no `type` column). This file exists to make the
alembic revision graph match reality; `upgrade()` mirrors the change
already live so a fresh database reaches the same state.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "0005_buyers_boolean_customer"
down_revision: str | Sequence[str] | None = "0004_owner_dashboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "buyers",
        sa.Column("is_customer", sa.Boolean(), nullable=True, server_default=sa.false()),
    )
    op.execute("UPDATE buyers SET is_customer = (type = 'customer')")
    op.alter_column("buyers", "is_customer", nullable=False)
    op.drop_constraint("ck_buyers_type", "buyers", type_="check")
    op.drop_column("buyers", "type")


def downgrade() -> None:
    op.add_column(
        "buyers",
        sa.Column("type", sa.String(length=16), nullable=True, server_default="lead"),
    )
    op.execute("UPDATE buyers SET type = CASE WHEN is_customer THEN 'customer' ELSE 'lead' END")
    op.alter_column("buyers", "type", nullable=False)
    op.create_check_constraint("ck_buyers_type", "buyers", "type IN ('lead', 'customer')")
    op.drop_column("buyers", "is_customer")
    op.create_check_constraint("ck_buyers_type", "buyers", "type IN ('lead', 'customer')")
    op.drop_column("buyers", "is_customer")
