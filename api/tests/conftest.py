"""DB fixtures. Uses TEST_DATABASE_URL (CI Postgres service) or an embedded pgserver (local dev).

Each session gets a fresh database migrated with alembic; the app connects as the limited medora_app role.
Each test gets its own synthetic hospital, so tests never see each other's data.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import psycopg
import pytest

API = Path(__file__).resolve().parents[1]


def _with_db(url: str, db: str, user: str | None = None, password: str | None = None) -> str:
    u = urlparse(url)
    netloc = u.netloc.split("@")[-1]
    cred = f"{user}:{password}@" if user else (u.netloc.split("@")[0] + "@" if "@" in u.netloc else "")
    return urlunparse(u._replace(netloc=cred + netloc, path=f"/{db}"))


@pytest.fixture(scope="session")
def pg():
    base = os.environ.get("TEST_DATABASE_URL")
    if not base:
        try:
            import pgserver
        except ImportError:
            pytest.skip("no TEST_DATABASE_URL and pgserver not installed")
        srv = pgserver.get_server(tempfile.mkdtemp(prefix="medora_pg_"), cleanup_mode="stop")
        base = srv.get_uri()
    db = f"medora_test_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(base, autocommit=True) as c:
        c.execute(f"CREATE DATABASE {db}")
    admin = _with_db(base, db)
    os.environ.update({"MIGRATION_DATABASE_URL": admin, "MEDORA_APP_PASSWORD": "test-app-pass",
                       "DATABASE_URL": admin, "JWT_SECRET": "test-secret-for-ci-only-0123456789abcdef", "MEDORA_LLM_MODE": "live",
                       "LLM_API_KEY": "", "ASR_API_KEY": "", "UPLOAD_DIR": str(Path(tempfile.mkdtemp()) / "uploads")})
    from alembic.config import Config

    from alembic import command

    cfg = Config(str(API / "alembic.ini"))
    cfg.set_main_option("script_location", str(API / "alembic"))
    command.upgrade(cfg, "head")
    os.environ["DATABASE_URL"] = _with_db(base, db, "medora_app", "test-app-pass")
    from medora import db as dbmod

    dbmod.pool.cache_clear()
    yield {"admin": admin, "app": os.environ["DATABASE_URL"]}
    dbmod.pool().close()
    dbmod.pool.cache_clear()


@pytest.fixture
def hospital(pg):
    from medora import seed
    from medora.db import tx

    with tx() as conn:
        hid = seed.create_hospital(conn, f"Test Hospital {uuid.uuid4().hex[:6]} (synthetic)")
    return hid


@pytest.fixture
def admin_conn(pg):
    with psycopg.connect(pg["admin"], autocommit=True) as c:
        yield c
