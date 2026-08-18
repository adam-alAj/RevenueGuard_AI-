"""Test configuration — sets environment to testing mode and provides db_session fixture.

This MUST be the first conftest loaded by pytest. It sets APP_ENV=testing
so that the Settings validator allows empty secrets during test runs.
"""

from __future__ import annotations

import os

# Set testing mode BEFORE any app imports
os.environ["APP_ENV"] = "testing"
os.environ["JWT_SECRET"] = "test-jwt-secret-not-for-production"
os.environ["GEMINI_API_KEY"] = "test-gemini-key-not-for-production"


import pytest_asyncio
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

# Import all models to register with Base.metadata
import app.models  # noqa: F401
from app.db.base import Base


@pytest_asyncio.fixture
async def db_session():
    """Provide an async database session using in-memory SQLite.

    Creates all tables before the test and drops them after.
    Registers type adaptors so JSONB columns render as JSON in SQLite.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)

    # Disable foreign key enforcement for testing (SQLite FK support is limited)
    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _rec):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.close()

    # Adapt JSONB → JSON for SQLite (column type compilation)
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def _adapt_jsonb(conn, cursor, stmt, params, context, executemany):
        pass  # JSONB stores fine as TEXT in SQLite

    # Replace JSONB type compilation for SQLite
    from sqlalchemy.sql import compiler as sa_compiler

    orig_visit_jsonb = getattr(
        sa_compiler.GenericTypeCompiler, "visit_JSONB", None
    )

    def _visit_jsonb(self, type_, **kw):
        return "JSON"

    sa_compiler.GenericTypeCompiler.visit_JSONB = _visit_jsonb

    # Also adapt UUID for SQLite
    def _visit_uuid(self, type_, **kw):
        return "CHAR(36)"

    sa_compiler.GenericTypeCompiler.visit_UUID = _visit_uuid

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        yield session

    # Restore original methods
    if orig_visit_jsonb:
        sa_compiler.GenericTypeCompiler.visit_JSONB = orig_visit_jsonb
    if hasattr(sa_compiler.GenericTypeCompiler, "visit_UUID"):
        delattr(sa_compiler.GenericTypeCompiler, "visit_UUID")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()
