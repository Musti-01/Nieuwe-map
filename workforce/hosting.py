"""Serialized release migrations for hosts without a release-command console."""
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import text


def migrate(engine):
    config = Config(str(Path(__file__).resolve().parent.parent / 'alembic.ini'))
    config.set_main_option('script_location', str(Path(__file__).resolve().parent.parent / 'migrations'))
    with engine.connect() as connection:
        # Session-level lock survives Alembic's transaction boundaries and serializes replicas.
        connection.execute(text('SELECT pg_advisory_lock(793125042)'))
        connection.commit()
        try:
            config.attributes['connection'] = connection
            command.upgrade(config, 'head')
            connection.commit()
        finally:
            connection.rollback()
            connection.execute(text('SELECT pg_advisory_unlock(793125042)'))
            connection.commit()
