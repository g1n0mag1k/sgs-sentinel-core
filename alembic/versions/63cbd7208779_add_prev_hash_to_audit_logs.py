"""add_prev_hash_to_audit_logs

Revision ID: 63cbd7208779
Revises: 5d31044de544
Create Date: 2026-05-02 12:27:28.768377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '63cbd7208779'
down_revision: Union[str, Sequence[str], None] = '5d31044de544'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "audit_logs",
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("audit_logs", "prev_hash")
