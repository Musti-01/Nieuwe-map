"""Automatically process completed shifts.

Revision ID: 0012
Revises: 0011
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE work_entries
        SET review_status = 'approved',
            reviewed_by = user_id,
            reviewed_at = ended_at
        WHERE ended_at IS NOT NULL
          AND review_status = 'pending'
    """)


def downgrade():
    # Data-only migration. Automatically processed shifts are not reverted.
    pass
