"""Effective monthly salary settings; no external payments."""
from alembic import op
import sqlalchemy as sa

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('salary_rates',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('basis', sa.String(10), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('effective_from', sa.Date(), nullable=False),
        sa.Column('changed_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('changed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['branch_id', 'user_id'], ['memberships.branch_id', 'memberships.user_id']),
        sa.UniqueConstraint('branch_id', 'user_id', 'effective_from', name='salary_rate_month'),
        sa.CheckConstraint("kind IN ('hourly', 'monthly')", name='salary_kind'),
        sa.CheckConstraint("basis IN ('gross', 'net')", name='salary_basis'),
        sa.CheckConstraint('amount > 0 AND amount <= 1000000', name='salary_amount'),
        sa.CheckConstraint('EXTRACT(DAY FROM effective_from) = 1', name='salary_effective_month'))
    op.create_index('ix_salary_rates_branch_id', 'salary_rates', ['branch_id'])
    op.create_index('ix_salary_rates_user_id', 'salary_rates', ['user_id'])


def downgrade():
    op.drop_table('salary_rates')
