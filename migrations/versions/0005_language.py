"""Persist the user's chosen interface language."""
from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('users',sa.Column('language',sa.String(2),nullable=False,server_default='nl'))
    op.alter_column('users','language',server_default=None)
    op.create_check_constraint('user_language','users',"language IN ('nl','fr','en','de','es')")

def downgrade():
    op.drop_constraint('user_language','users',type_='check')
    op.drop_column('users','language')
