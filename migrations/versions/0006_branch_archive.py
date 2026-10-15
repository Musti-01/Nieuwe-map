"""Retain branch history when removing operational access."""
from alembic import op
import sqlalchemy as sa
revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('branches', sa.Column('archived_at', sa.DateTime(timezone=True)))
    op.add_column('branches', sa.Column('archived_by', sa.Integer()))
    op.create_foreign_key('branch_archived_by', 'branches', 'users', ['archived_by'], ['id'])

def downgrade():
    op.drop_constraint('branch_archived_by', 'branches', type_='foreignkey')
    op.drop_column('branches', 'archived_by')
    op.drop_column('branches', 'archived_at')
