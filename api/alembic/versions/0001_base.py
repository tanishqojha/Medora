"""base schema

Revision ID: 0001
"""
from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    op.execute((SQL / "0001_base.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    # Base schema holds append-only tables (events, audit_log). Dropping them loses events.
    raise RuntimeError("0001 is not reversible: it would drop append-only tables. Stop and ask.")
