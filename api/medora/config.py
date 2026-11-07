"""Settings from env and config/*.yaml. Values marked proposed in YAML stay proposed until a baseline run."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")
load_dotenv(ROOT / "api" / ".env")


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _sqlalchemy(url: str) -> str:
    return url.replace("postgresql://", "postgresql+psycopg://", 1) if url.startswith("postgresql://") else url


def database_url() -> str:
    url = env("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL is not set. Copy .env.example to .env and fill the session pooler URL.")
    if ":6543/" in url:
        raise RuntimeError("DATABASE_URL points at the transaction pooler (6543). Use the session pooler (5432).")
    return url


def migration_url() -> str:
    return _sqlalchemy(env("MIGRATION_DATABASE_URL") or database_url())


@lru_cache
def load_yaml(name: str) -> Any:
    with open(ROOT / "config" / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def settings() -> dict[str, Any]:
    return load_yaml("settings.yaml")


def setting(path: str) -> Any:
    """Dotted lookup. Values may be {value: x, proposed: true}; returns x."""
    node: Any = settings()
    for part in path.split("."):
        node = node[part]
    if isinstance(node, dict) and "value" in node:
        return node["value"]
    return node
