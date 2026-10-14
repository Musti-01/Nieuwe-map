import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

load_dotenv()

def make_engine(url=None):
    url = url or os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("Stel DATABASE_URL in op een PostgreSQL URL.")
    parsed = make_url(url)
    if parsed.drivername not in ('postgres', 'postgresql', 'postgresql+psycopg'):
        raise RuntimeError("Stel DATABASE_URL in op een PostgreSQL URL.")
    return create_engine(parsed.set(drivername='postgresql+psycopg'), pool_pre_ping=True)

def sessions(engine):
    return sessionmaker(engine, expire_on_commit=False)
