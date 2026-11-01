"""Employee phone scan replay protection.

Revision ID: 0011
Revises: 0010
"""
from alembic import op
import sqlalchemy as sa

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "phone_qr_uses",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_phone_qr_uses_branch_id", "phone_qr_uses", ["branch_id"])
    op.create_index("ix_phone_qr_uses_user_id", "phone_qr_uses", ["user_id"])


def downgrade():
    op.drop_table("phone_qr_uses")
