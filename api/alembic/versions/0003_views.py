"""canonical patient and live event views

Revision ID: 0003
"""
from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SQL = Path(__file__).resolve().parents[1] / "sql"


def upgrade() -> None:
    op.execute((SQL / "0003_views.sql").read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS live_events")
    op.execute("DROP VIEW IF EXISTS patient_canonical")
    op.execute("DROP INDEX IF EXISTS events_supersedes_idx")
