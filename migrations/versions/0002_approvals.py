"""Mandatory approvals, platform owner and notification outbox.

Existing tenants become pending; no implicit grandfathered approval.
"""
from alembic import op
import sqlalchemy as sa
revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('platform_owner', sa.Boolean, nullable=False, server_default=sa.false()))
    # The previous bootstrap could create exactly one admin and had no delegation API.
    op.execute("UPDATE users SET platform_owner = true WHERE platform_admin = true AND (SELECT count(*) FROM users WHERE platform_admin = true) = 1")
    op.alter_column('users', 'platform_owner', server_default=None)
    for table, constraint in [('organizations', 'organization_status'), ('branches', 'branch_status')]:
        op.add_column(table, sa.Column('status', sa.String(20), nullable=False, server_default='pending'))
        op.add_column(table, sa.Column('address', sa.String(255), nullable=False, server_default=''))
        op.add_column(table, sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
        op.add_column(table, sa.Column('reviewed_by', sa.Integer, sa.ForeignKey('users.id')))
        op.add_column(table, sa.Column('reviewed_at', sa.DateTime(timezone=True)))
        op.create_check_constraint(constraint, table, "status IN ('pending', 'approved', 'rejected', 'blocked')")
        for col in ['status', 'address', 'submitted_at']:
            op.alter_column(table, col, server_default=None)
    op.add_column('organizations', sa.Column('contact_phone', sa.String(40), nullable=False, server_default=''))
    op.alter_column('organizations', 'contact_phone', server_default=None)
    op.create_table('approval_decisions', sa.Column('id', sa.Integer, primary_key=True), sa.Column('organization_id', sa.Integer, sa.ForeignKey('organizations.id'), nullable=False), sa.Column('branch_id', sa.Integer, sa.ForeignKey('branches.id')), sa.Column('reviewer_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False), sa.Column('previous_status', sa.String(20), nullable=False), sa.Column('status', sa.String(20), nullable=False), sa.Column('reason', sa.String(500), nullable=False), sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False))
    op.create_table('notifications', sa.Column('id', sa.Integer, primary_key=True), sa.Column('decision_id', sa.Integer, sa.ForeignKey('approval_decisions.id'), nullable=False, unique=True), sa.Column('recipient', sa.String(254), nullable=False), sa.Column('subject', sa.String(200), nullable=False), sa.Column('body', sa.String(2000), nullable=False), sa.Column('sent_at', sa.DateTime(timezone=True)), sa.Column('attempts', sa.Integer, nullable=False))

def downgrade():
    op.drop_table('notifications')
    op.drop_table('approval_decisions')
    op.drop_column('organizations', 'contact_phone')
    for table, constraint in [('organizations', 'organization_status'), ('branches', 'branch_status')]:
        op.drop_constraint(constraint, table, type_='check')
        for col in ['status', 'address', 'submitted_at', 'reviewed_by', 'reviewed_at']:
            op.drop_column(table, col)
    op.drop_column('users', 'platform_owner')
