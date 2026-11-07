"""app role, grants, RLS

Revision ID: 0002
"""
from pathlib import Path

from psycopg import sql

from alembic import op
from medora.config import env

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    password = env("MEDORA_APP_PASSWORD")
    if not password or password == "change-me":
        raise RuntimeError("Set MEDORA_APP_PASSWORD in .env before running migrations.")
    literal = sql.Literal(password).as_string(None)
    op.execute((SQL / "0002_app_role.sql").read_text(encoding="utf-8").replace(":app_password", literal))


def downgrade() -> None:
    op.execute("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM medora_app")
    op.execute("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM medora_app")
    op.execute("REVOKE USAGE ON SCHEMA public FROM medora_app")
