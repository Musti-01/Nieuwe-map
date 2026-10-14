#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# A local development database is generated only when no configuration exists.
if [[ ! -f .env && -z "${DATABASE_URL:-}" ]]; then
  .venv/bin/python - <<'PY'
import os, secrets
from pathlib import Path
password = secrets.token_urlsafe(32)
with os.fdopen(os.open('.env', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as f:
    f.write(f'LOCAL_DATABASE=1\nPOSTGRES_PASSWORD={password}\nDATABASE_URL=postgresql+psycopg://workforce:{password}@localhost:5432/workforce\nAPP_TIMEZONE=Europe/Brussels\n')
PY
fi
if [[ -n "${DATABASE_URL:-}" ]]; then
  local_db=0
else
local_db=$(.venv/bin/python - <<'PY'
import os
from dotenv import load_dotenv
load_dotenv('.env')
print('1' if not os.environ.get('DATABASE_URL') else os.environ.get('LOCAL_DATABASE', '0'))
PY
)
fi
if [[ "$local_db" == "1" ]]; then
  docker compose up -d --wait db
fi
.venv/bin/python - <<'PY'
from workforce.db import make_engine
from sqlalchemy import text
with make_engine().connect() as c:
    assert c.scalar(text('SELECT 1')) == 1
print('PostgreSQL bereikbaar.')
PY
.venv/bin/alembic upgrade head
exec .venv/bin/streamlit run app.py --server.address=0.0.0.0 --server.port="${PORT:-8501}" --browser.gatherUsageStats=false
