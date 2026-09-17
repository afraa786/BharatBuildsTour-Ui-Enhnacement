"""Add runs, run_events, approvals, and whatsapp_messages tables."""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_runs_manager"
down_revision: str | tuple[str, ...] | None = "0001_baseline"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.execute("CREATE SEQUENCE run_number_seq START WITH 1000 INCREMENT BY 1")

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("buyer_wa_id", sa.String(), nullable=False),
        sa.Column("buyer_name", sa.String(), nullable=True),
        sa.Column("raw_text", sa.String(), nullable=True),
        sa.Column("line_items", postgresql.JSONB(), nullable=False),
        sa.Column("quote_snapshot", postgresql.JSONB(), nullable=True),
        sa.Column("quote_id", sa.String(), nullable=True),
        sa.Column("payment_id", sa.String(), nullable=True),
        sa.Column("invoice_id", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("run_id"),
    )
    op.create_index("ix_runs_run_id", "runs", ["run_id"])
    op.create_index("ix_runs_buyer_wa_id", "runs", ["buyer_wa_id"])

    op.create_table(
        "run_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False
        ),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_run_events_run_id", "run_events", ["run_id"])

    op.create_table(
        "approvals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("runs.id"), nullable=False
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("bound_run_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("actor", sa.String(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_approvals_run_id", "approvals", ["run_id"])

    op.create_table(
        "whatsapp_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("provider_message_id", sa.String(), nullable=False),
        sa.Column("direction", sa.String(), nullable=False),
        sa.Column("wa_id", sa.String(), nullable=False),
        sa.Column("phone_number_id", sa.String(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("provider_message_id"),
    )
    op.create_index(
        "ix_whatsapp_messages_provider_message_id", "whatsapp_messages", ["provider_message_id"]
    )
    op.create_index("ix_whatsapp_messages_wa_id", "whatsapp_messages", ["wa_id"])


def downgrade() -> None:
    op.drop_table("whatsapp_messages")
    op.drop_table("approvals")
    op.drop_table("run_events")
    op.drop_table("runs")
    op.execute("DROP SEQUENCE run_number_seq")
