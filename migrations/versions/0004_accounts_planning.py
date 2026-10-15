"""Account lifecycle, invitations, reset tokens and planned shifts."""
from alembic import op
import sqlalchemy as sa
revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('users', sa.Column('is_active',sa.Boolean,nullable=False,server_default=sa.true()))
    op.alter_column('users','is_active',server_default=None)
    op.alter_column('notifications','decision_id',nullable=True)
    op.create_table('account_tokens',sa.Column('token_hash',sa.String(64),primary_key=True),sa.Column('purpose',sa.String(20),nullable=False),sa.Column('email',sa.String(254),nullable=False),sa.Column('user_id',sa.Integer,sa.ForeignKey('users.id')),sa.Column('branch_id',sa.Integer,sa.ForeignKey('branches.id')),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id')),sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),sa.Column('consumed_at',sa.DateTime(timezone=True)),sa.CheckConstraint("purpose IN ('invite', 'reset')",name='account_token_purpose'))
    op.create_table('shift_plans',sa.Column('id',sa.Integer,primary_key=True),sa.Column('branch_id',sa.Integer,nullable=False),sa.Column('user_id',sa.Integer,nullable=False),sa.Column('starts_at',sa.DateTime(timezone=True),nullable=False),sa.Column('ends_at',sa.DateTime(timezone=True),nullable=False),sa.Column('created_by',sa.Integer,sa.ForeignKey('users.id'),nullable=False),sa.Column('status',sa.String(20),nullable=False),sa.Column('note',sa.String(500),nullable=False),sa.Column('version',sa.Integer,nullable=False),sa.ForeignKeyConstraint(['branch_id','user_id'],['memberships.branch_id','memberships.user_id']),sa.CheckConstraint('ends_at > starts_at',name='plan_interval'),sa.CheckConstraint("status IN ('scheduled', 'cancelled')",name='plan_status'))
    op.create_index('ix_shift_plans_branch_id','shift_plans',['branch_id'])
    op.create_index('ix_shift_plans_user_id','shift_plans',['user_id'])
    op.add_column('work_entries',sa.Column('plan_id',sa.Integer,sa.ForeignKey('shift_plans.id'),unique=True))

def downgrade():
    if op.get_bind().scalar(sa.text('SELECT count(*) FROM notifications WHERE decision_id IS NULL')):
        raise RuntimeError('Archiveer algemene notificaties expliciet voordat je terugmigreert naar 0003.')
    op.drop_column('work_entries','plan_id')
    op.drop_table('shift_plans')
    op.drop_table('account_tokens')
    op.alter_column('notifications','decision_id',nullable=False)
    op.drop_column('users','is_active')
