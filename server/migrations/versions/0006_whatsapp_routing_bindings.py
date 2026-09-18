"""Add trusted receiving-number bindings and Meta delivery status records.

Revision ID: 0006_whatsapp_routing_bindings
Revises: 0006_buyer_cart_sessions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0006_whatsapp_routing_bindings"
down_revision: str | Sequence[str] | None = "0006_buyer_cart_sessions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("whatsapp_messages", sa.Column("business_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_whatsapp_messages_business",
        "whatsapp_messages",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_whatsapp_messages_business_created", "whatsapp_messages", ["business_id", "created_at"]
    )
    op.create_table(
        "whatsapp_number_bindings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), server_default="meta_whatsapp", nullable=False),
        sa.Column("phone_number_id", sa.String(128), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("experience", sa.String(32), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("waba_id", sa.String(128)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "experience IN ('owner_manager', 'customer_commerce')",
            name="ck_whatsapp_number_bindings_experience",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "phone_number_id", name="uq_whatsapp_number_bindings_provider_phone"
        ),
    )
    op.create_index(
        "ix_whatsapp_number_bindings_business", "whatsapp_number_bindings", ["business_id"]
    )
    op.create_table(
        "whatsapp_message_statuses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(32), server_default="meta_whatsapp", nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("phone_number_id", sa.String(128)),
        sa.Column("recipient_wa_id", sa.String(64)),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True)),
        sa.Column("payload", postgresql.JSONB()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('sent', 'delivered', 'read', 'failed')",
            name="ck_whatsapp_message_statuses_status",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "provider_message_id", "status", name="uq_whatsapp_message_statuses_event"
        ),
    )
    op.create_index(
        "ix_whatsapp_message_statuses_phone", "whatsapp_message_statuses", ["phone_number_id"]
    )
    op.create_index(
        "ix_whatsapp_message_statuses_business", "whatsapp_message_statuses", ["business_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_whatsapp_message_statuses_business", table_name="whatsapp_message_statuses")
    op.drop_index("ix_whatsapp_message_statuses_phone", table_name="whatsapp_message_statuses")
    op.drop_table("whatsapp_message_statuses")
    op.drop_index("ix_whatsapp_number_bindings_business", table_name="whatsapp_number_bindings")
    op.drop_table("whatsapp_number_bindings")
    op.drop_index("ix_whatsapp_messages_business_created", table_name="whatsapp_messages")
    op.drop_constraint("fk_whatsapp_messages_business", "whatsapp_messages", type_="foreignkey")
    op.drop_column("whatsapp_messages", "business_id")
