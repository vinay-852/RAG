#!/usr/bin/env bash
set -euo pipefail

python - <<'PY'
import os
import time

import psycopg

database_url = os.environ["DATABASE_URL"]
for attempt in range(60):
    try:
        with psycopg.connect(database_url) as conn:
            conn.execute("SELECT 1")
        print("Postgres is ready")
        break
    except Exception as exc:
        if attempt == 59:
            raise
        print(f"Waiting for Postgres: {exc}")
        time.sleep(2)
PY

python -m backend.ingest --reset
exec uvicorn backend.app:app --host 0.0.0.0 --port 8000
