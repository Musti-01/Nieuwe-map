from concurrent.futures import ThreadPoolExecutor
from sqlalchemy import text
from workforce.db import make_engine
from workforce.hosting import migrate


def test_provider_database_urls_use_psycopg_and_keep_tls():
    for prefix in ('postgres', 'postgresql', 'postgresql+psycopg'):
        engine = make_engine(f'{prefix}://user:example@database.example/workforce?sslmode=verify-full')
        assert engine.url.drivername == 'postgresql+psycopg'
        assert engine.url.query['sslmode'] == 'verify-full'
        engine.dispose()


def test_cloud_migrations_are_repeatable_and_serialized(engine):
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(lambda _: migrate(engine), range(2)))
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0002'
