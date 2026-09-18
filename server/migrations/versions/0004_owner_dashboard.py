"""Add owner dashboard identity, categories, and business-scoped run fields.

Revision ID: 0004_owner_dashboard
Revises: 0003_merge_phase1_heads
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_owner_dashboard"
down_revision: str | Sequence[str] | None = "0003_merge_phase1_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("phone_number", sa.String(32), nullable=False, unique=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_users_phone_number", "users", ["phone_number"])
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "business_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("businesses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("business_id", "name", name="uq_categories_business_name"),
    )
    op.add_column(
        "products", sa.Column("category_id", postgresql.UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        "fk_products_category",
        "products",
        "categories",
        ["category_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_products_business_category", "products", ["business_id", "category_id"])
    op.add_column("buyers", sa.Column("type", sa.String(16), nullable=False, server_default="lead"))
    op.add_column("buyers", sa.Column("source", sa.String(64), nullable=True))
    op.add_column(
        "buyers", sa.Column("last_contacted_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint("ck_buyers_type", "buyers", "type IN ('lead', 'customer')")
    # Existing workflow runs have no business relation. Keep historic rows readable in
    # the DB but only surface explicitly business-scoped rows to owner APIs.
    op.add_column("runs", sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_runs_business", "runs", "businesses", ["business_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_runs_business_status", "runs", ["business_id", "status"])
    op.add_column(
        "runs", sa.Column("expected_delivery_date", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_index("ix_runs_business_status", table_name="runs")
    op.drop_constraint("fk_runs_business", "runs", type_="foreignkey")
    op.drop_column("runs", "expected_delivery_date")
    op.drop_column("runs", "business_id")
    op.drop_constraint("ck_buyers_type", "buyers", type_="check")
    op.drop_column("buyers", "last_contacted_at")
    op.drop_column("buyers", "source")
    op.drop_column("buyers", "type")
    op.drop_index("ix_products_business_category", table_name="products")
    op.drop_constraint("fk_products_category", "products", type_="foreignkey")
    op.drop_column("products", "category_id")
    op.drop_table("categories")
    op.drop_index("ix_users_phone_number", table_name="users")
    op.drop_table("users")
