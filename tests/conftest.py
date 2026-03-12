"""Shared pytest fixtures for the purser test suite."""

from pathlib import Path

import duckdb
import pytest

DB_PATH = Path(__file__).parent / "test-warehouse.db"


@pytest.fixture(scope="session")
def test_warehouse() -> duckdb.DuckDBPyConnection:
    """Return a persistent DuckDB connection to tests/test-warehouse.db.

    Session-scoped: connection is opened once per test run and never torn down.
    The database file is persistent across runs; individual tests that write
    data are responsible for cleaning up their own rows/tables.
    """
    conn = duckdb.connect(str(DB_PATH))
    yield conn
    conn.close()
