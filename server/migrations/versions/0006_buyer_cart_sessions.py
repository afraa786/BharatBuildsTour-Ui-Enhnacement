"""Add buyer_cart_sessions for the guided WhatsApp ordering flow.

Revision ID: 0006_buyer_cart_sessions
Revises: 0005_buyers_boolean_customer
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_buyer_cart_sessions"
down_revision: str | Sequence[str] | None = "0005_buyers_boolean_customer"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "buyer_cart_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("wa_id", sa.String(), nullable=False),
        sa.Column("phone_number_id", sa.String(), nullable=True),
        sa.Column("step", sa.String(), nullable=False, server_default="IDLE"),
        sa.Column("pending_sku", sa.String(), nullable=True),
        sa.Column("cart", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("last_prompt", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_buyer_cart_sessions_wa_id", "buyer_cart_sessions", ["wa_id"])


def downgrade() -> None:
    op.drop_index("ix_buyer_cart_sessions_wa_id", table_name="buyer_cart_sessions")
    op.drop_table("buyer_cart_sessions")
