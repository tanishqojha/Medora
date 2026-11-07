"""Dev only: run Postgres locally (pip-packaged, no Docker) until Supabase is set up. Prints env lines to source.

Usage: eval "$(uv run --project api python scripts/local_pg.py)"   then migrate and run as usual.
Data lives in data/pg (git-ignored). The app still connects as the limited medora_app role.
"""
from pathlib import Path

import pgserver  # dev dependency
import psycopg

ROOT = Path(__file__).resolve().parents[1]
srv = pgserver.get_server(str(ROOT / "data" / "pg"), cleanup_mode=None)
base = srv.get_uri()
with psycopg.connect(base, autocommit=True) as c:
    if not c.execute("SELECT 1 FROM pg_database WHERE datname = 'medora'").fetchone():
        c.execute("CREATE DATABASE medora")
    if c.execute("SELECT 1 FROM pg_roles WHERE rolname = 'medora_app'").fetchone():
        c.execute("ALTER ROLE medora_app PASSWORD 'localdev'")  # local only; keeps the printed URL valid
admin = base.rsplit("/", 1)[0] + "/medora"
print(f"export MIGRATION_DATABASE_URL='{admin}'")
print(f"export DATABASE_URL='{admin.replace('postgres:@', 'medora_app:localdev@')}'")
print("export MEDORA_APP_PASSWORD=localdev")
print("export JWT_SECRET=local-dev-only-secret-0123456789abcdef")
print("export PYTHONIOENCODING=utf-8")
