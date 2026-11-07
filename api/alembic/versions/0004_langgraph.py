"""LangGraph checkpoint tables for approval gates (S11)

Revision ID: 0004
"""
from langgraph.checkpoint.postgres import PostgresSaver

from alembic import op
from medora.config import env

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TABLES = ("checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations")


def upgrade() -> None:
    url = env("MIGRATION_DATABASE_URL") or env("DATABASE_URL")
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
    for t in TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {t} TO medora_app")
        op.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS medora_app_all ON {t}")
        op.execute(f"CREATE POLICY medora_app_all ON {t} TO medora_app USING (true) WITH CHECK (true)")


def downgrade() -> None:
    for t in TABLES:
        op.execute(f"DROP TABLE IF EXISTS {t}")
