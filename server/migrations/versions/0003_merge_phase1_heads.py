"""Merge Rehbar workflow and Fareed commercial migration heads.

Revision ID: 0003_merge_phase1_heads
Revises: 0002_runs_manager, 0002_commercial_schema
"""

from collections.abc import Sequence

revision: str = "0003_merge_phase1_heads"
down_revision: str | Sequence[str] | None = (
    "0002_runs_manager",
    "0002_commercial_schema",
)
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Both parent revisions already contain their complete schema changes."""


def downgrade() -> None:
    """Downgrading the merge point restores the two independent heads."""
