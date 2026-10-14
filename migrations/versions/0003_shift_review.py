"""Explicit approval and immutable correction history for worked shifts."""
from alembic import op
import sqlalchemy as sa
revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('work_entries', sa.Column('review_status', sa.String(20), nullable=False, server_default='pending'))
    op.add_column('work_entries', sa.Column('version', sa.Integer, nullable=False, server_default='1'))
    op.add_column('work_entries', sa.Column('reviewed_by', sa.Integer, sa.ForeignKey('users.id')))
    op.add_column('work_entries', sa.Column('reviewed_at', sa.DateTime(timezone=True)))
    op.alter_column('work_entries', 'review_status', server_default=None)
    op.alter_column('work_entries', 'version', server_default=None)
    op.create_check_constraint('shift_review_status', 'work_entries', "review_status IN ('pending', 'approved')")
    op.create_check_constraint('approved_shift_complete', 'work_entries', "review_status != 'approved' OR (ended_at IS NOT NULL AND reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)")
    op.create_table('shift_reviews',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('entry_id', sa.Integer, sa.ForeignKey('work_entries.id'), nullable=False),
        sa.Column('reviewer_id', sa.Integer, sa.ForeignKey('users.id'), nullable=False),
        sa.Column('action', sa.String(20), nullable=False),
        sa.Column('reason', sa.String(500), nullable=False),
        sa.Column('old_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('old_end', sa.DateTime(timezone=True)),
        sa.Column('new_start', sa.DateTime(timezone=True), nullable=False),
        sa.Column('new_end', sa.DateTime(timezone=True), nullable=False),
        sa.Column('previous_status', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_shift_reviews_entry_id','shift_reviews',['entry_id'])

def downgrade():
    op.drop_table('shift_reviews')
    op.drop_constraint('approved_shift_complete', 'work_entries', type_='check')
    op.drop_constraint('shift_review_status', 'work_entries', type_='check')
    for col in ['reviewed_at','reviewed_by','version','review_status']:
        op.drop_column('work_entries', col)
