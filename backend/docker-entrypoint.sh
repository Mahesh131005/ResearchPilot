#!/bin/sh
set -e

echo "==> Waiting for database to be ready..."
python - << 'EOF'
import os
import sys
import time
from urllib.parse import urlparse
import psycopg2

app_env = os.environ.get("APP_ENV", "development").lower()
db_url = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL")

if not db_url:
    if app_env == "production":
        print("FATAL CONFIGURATION ERROR: DATABASE_URL is missing in production environment.", file=sys.stderr)
        sys.exit(1)
    db_url = "postgresql+psycopg2://postgres:postgres@db:5432/researchpilot"

# Convert to standard psycopg2 connection string
conn_str = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
if "ssl=require" in conn_str:
    conn_str = conn_str.replace("ssl=require", "sslmode=require")

# Safe diagnostic (host, port, db name ONLY - credentials NEVER printed)
try:
    clean = conn_str.split("://", 1)[-1] if "://" in conn_str else conn_str
    parsed = urlparse(f"http://{clean}")
    target_host = parsed.hostname or "unknown"
    target_port = parsed.port or 5432
    target_db = parsed.path.lstrip("/") or "unknown"
except Exception:
    target_host, target_port, target_db = "unknown", 5432, "unknown"

print(f"==> Database pre-flight target: host={target_host}, port={target_port}, database={target_db} (credentials omitted)")

if app_env == "production" and (target_host in ("localhost", "127.0.0.1", "::1", "0.0.0.0") or target_port == 5433):
    print(f"FATAL CONFIGURATION ERROR: Production database target cannot be localhost or port 5433 ({target_host}:{target_port}).", file=sys.stderr)
    print("Please verify that Render injected DATABASE_URL correctly from researchpilot-db.", file=sys.stderr)
    sys.exit(1)

max_retries = 30
retry_interval = 2

for i in range(max_retries):
    try:
        conn = psycopg2.connect(conn_str)
        # Ensure pgvector extension is present before running Alembic
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        conn.commit()
        conn.close()
        print(f"==> Database at {target_host}:{target_port} is reachable and ready (pgvector extension verified)!")
        sys.exit(0)
    except Exception as e:
        print(f"Waiting for database at {target_host}:{target_port} ({i+1}/{max_retries}): {e}")
        time.sleep(retry_interval)

print(f"==> Database connection to {target_host}:{target_port} timed out after 60s", file=sys.stderr)
sys.exit(1)
EOF

echo "==> Running database migrations (Alembic)..."
export SYNC_DATABASE_URL="${SYNC_DATABASE_URL:-$DATABASE_URL}"
alembic upgrade head

echo "==> Starting ResearchPilot backend server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

