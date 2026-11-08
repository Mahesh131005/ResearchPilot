#!/bin/sh
set -e

echo "==> Waiting for database to be ready..."
python - << 'EOF'
import os
import sys
import time
import psycopg2

db_url = os.environ.get("SYNC_DATABASE_URL") or os.environ.get("DATABASE_URL", "postgresql+psycopg2://postgres:postgres@db:5432/researchpilot")
# Convert to standard psycopg2 connection string
conn_str = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
if "ssl=require" in conn_str:
    conn_str = conn_str.replace("ssl=require", "sslmode=require")

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
        print("==> Database is reachable and ready (pgvector extension verified)!")
        sys.exit(0)
    except Exception as e:
        print(f"Waiting for database ({i+1}/{max_retries}): {e}")
        time.sleep(retry_interval)

print("==> Database connection timed out after 60s")
sys.exit(1)
EOF

echo "==> Running database migrations (Alembic)..."
alembic upgrade head

echo "==> Starting ResearchPilot backend server..."
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"

