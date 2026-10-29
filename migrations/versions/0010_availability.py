"""Employee availability slots

Revision ID: 0010_availability
Revises: 0009_salary_rates
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_availability"
down_revision = "0009_salary_rates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "employee_availability",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("branch_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["branch_id", "user_id"], ["memberships.branch_id", "memberships.user_id"]),
        sa.CheckConstraint("ends_at > starts_at", name="availability_interval"),
    )
    op.create_index("ix_employee_availability_branch_id", "employee_availability", ["branch_id"])
    op.create_index("ix_employee_availability_user_id", "employee_availability", ["user_id"])


def downgrade():
    op.drop_index("ix_employee_availability_user_id", table_name="employee_availability")
    op.drop_index("ix_employee_availability_branch_id", table_name="employee_availability")
    op.drop_table("employee_availability")
