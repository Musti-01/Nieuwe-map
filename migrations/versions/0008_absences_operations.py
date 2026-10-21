"""Absences, medical document retention and operational monitoring."""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('notifications', sa.Column('expires_at', sa.DateTime(timezone=True)))
    op.create_table('absences',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(10), nullable=False),
        sa.Column('starts_on', sa.Date(), nullable=False),
        sa.Column('ends_on', sa.Date(), nullable=False),
        sa.Column('status', sa.String(12), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_by', sa.Integer(), sa.ForeignKey('users.id')),
        sa.ForeignKeyConstraint(['branch_id', 'user_id'], ['memberships.branch_id', 'memberships.user_id']),
        sa.CheckConstraint('ends_on >= starts_on', name='absence_interval'),
        sa.CheckConstraint("kind IN ('sick', 'leave')", name='absence_kind'),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'cancelled')", name='absence_status'))
    op.create_index('ix_absences_branch_id', 'absences', ['branch_id'])
    op.create_index('ix_absences_user_id', 'absences', ['user_id'])
    op.add_column('sick_notes', sa.Column('absence_id', sa.Integer(), sa.ForeignKey('absences.id', name='sick_note_absence')))
    op.add_column('sick_notes', sa.Column('expires_at', sa.DateTime(timezone=True)))
    # Existing documents receive a finite, documented retention window.
    op.execute("UPDATE sick_notes SET expires_at = uploaded_at + interval '30 days'")
    op.alter_column('sick_notes', 'expires_at', nullable=False)
    op.create_table('system_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('category', sa.String(20), nullable=False),
        sa.Column('code', sa.String(80), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_system_events_occurred_at', 'system_events', ['occurred_at'])


def downgrade():
    op.drop_column('notifications', 'expires_at')
    op.drop_table('system_events')
    op.drop_column('sick_notes', 'expires_at')
    op.drop_constraint('sick_note_absence', 'sick_notes', type_='foreignkey')
    op.drop_column('sick_notes', 'absence_id')
    op.drop_table('absences')
