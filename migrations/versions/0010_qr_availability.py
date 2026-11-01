"""Secure scanner clock-in and employee availability.

Revision ID: 0010
Revises: 0009
"""
from alembic import op
import sqlalchemy as sa

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "scanner_devices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_scanner_devices_branch_id", "scanner_devices", ["branch_id"])

    op.create_table(
        "qr_scan_uses",
        sa.Column("token_hash", sa.String(64), primary_key=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("scanner_id", sa.Integer(), sa.ForeignKey("scanner_devices.id"), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_qr_scan_uses_branch_id", "qr_scan_uses", ["branch_id"])
    op.create_index("ix_qr_scan_uses_user_id", "qr_scan_uses", ["user_id"])

    op.create_table(
        "employee_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("weekly", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recurrence_until", sa.Date()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]),
        sa.CheckConstraint("ends_at > starts_at", name="availability_interval"),
        sa.CheckConstraint(
            "(weekly = false AND recurrence_until IS NULL) OR "
            "(weekly = true AND recurrence_until IS NOT NULL)",
            name="availability_recurrence",
        ),
    )
    op.create_index("ix_employee_availability_branch_id", "employee_availability", ["branch_id"])
    op.create_index("ix_employee_availability_user_id", "employee_availability", ["user_id"])


def downgrade():
    op.drop_table("employee_availability")
    op.drop_table("qr_scan_uses")
    op.drop_table("scanner_devices")
