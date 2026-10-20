"""Store private employee sick notes in PostgreSQL."""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('sick_notes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('branch_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(120), nullable=False),
        sa.Column('media_type', sa.String(40), nullable=False),
        sa.Column('content', sa.LargeBinary(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['branch_id', 'user_id'], ['memberships.branch_id', 'memberships.user_id']),
        sa.CheckConstraint('octet_length(content) BETWEEN 1 AND 5242880', name='sick_note_size'),
        sa.CheckConstraint("media_type IN ('application/pdf', 'image/png', 'image/jpeg')", name='sick_note_type'))
    op.create_index('ix_sick_notes_branch_id', 'sick_notes', ['branch_id'])
    op.create_index('ix_sick_notes_user_id', 'sick_notes', ['user_id'])


def downgrade():
    op.drop_table('sick_notes')
