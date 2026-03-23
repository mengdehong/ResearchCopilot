"""add_run_snapshot_interrupt_cot_fields

Revision ID: 02cb5510215f
Revises: 2e3f305b4dab
Create Date: 2026-03-22 23:48:25.552927

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "02cb5510215f"
down_revision: str | Sequence[str] | None = "2e3f305b4dab"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add interrupt_data, cot_nodes, content_blocks to run_snapshots."""
    op.add_column("run_snapshots", sa.Column("interrupt_data", sa.JSON(), nullable=True))
    op.add_column("run_snapshots", sa.Column("cot_nodes", sa.JSON(), nullable=True))
    op.add_column("run_snapshots", sa.Column("content_blocks", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Remove interrupt_data, cot_nodes, content_blocks from run_snapshots."""
    op.drop_column("run_snapshots", "content_blocks")
    op.drop_column("run_snapshots", "cot_nodes")
    op.drop_column("run_snapshots", "interrupt_data")
