from pathlib import Path

import pytest

from backend.repositories.postgres import PostgresRepository, normalize_dsn


def test_normalize_dsn_accepts_asyncpg_style_database_url():
    assert normalize_dsn("postgresql+asyncpg://app:app@db:5432/app") == "postgresql://app:app@db:5432/app"


def test_postgres_repository_requires_database_url():
    with pytest.raises(ValueError, match="DATABASE_URL_REQUIRED"):
        PostgresRepository("")


def test_postgres_schema_contains_persistence_tables():
    schema = Path("backend/db/schema.sql").read_text(encoding="utf-8")

    assert "CREATE TABLE IF NOT EXISTS sessions" in schema
    assert "CREATE TABLE IF NOT EXISTS hint_events" in schema
    assert "CREATE TABLE IF NOT EXISTS master_requests" in schema
    assert "CREATE TABLE IF NOT EXISTS idempotency_records" in schema
