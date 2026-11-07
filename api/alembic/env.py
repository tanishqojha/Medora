"""Alembic env. Migrations run as the admin user (MIGRATION_DATABASE_URL), never from app code."""
from sqlalchemy import create_engine, pool

from alembic import context
from medora.config import migration_url

config = context.config


def run_migrations_offline() -> None:
    context.configure(url=migration_url(), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(migration_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, transaction_per_migration=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
