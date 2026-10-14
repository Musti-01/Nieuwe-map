from alembic import context
from workforce.db import make_engine
from workforce.models import Base

def run(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()

provided = context.config.attributes.get('connection')
if provided is not None:
    run(provided)
else:
    with make_engine().connect() as connection:
        run(connection)
