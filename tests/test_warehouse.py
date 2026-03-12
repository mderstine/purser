"""Smoke tests for the test_warehouse DuckDB fixture."""

from pathlib import Path

import duckdb


def test_warehouse_connects(test_warehouse: duckdb.DuckDBPyConnection) -> None:
    """Fixture returns a live DuckDB connection."""
    result = test_warehouse.execute("SELECT 42 AS answer").fetchone()
    assert result is not None
    assert result[0] == 42


def test_warehouse_file_exists() -> None:
    """Database file is created at the expected path."""
    db_path = Path(__file__).parent / "test-warehouse.db"
    assert db_path.exists(), f"Expected {db_path} to exist after fixture runs"


def test_warehouse_create_and_drop(test_warehouse: duckdb.DuckDBPyConnection) -> None:
    """Tests that write data clean up after themselves."""
    test_warehouse.execute("CREATE TABLE IF NOT EXISTS _smoke_test (id INTEGER, label VARCHAR)")
    test_warehouse.execute("INSERT INTO _smoke_test VALUES (1, 'hello')")
    row = test_warehouse.execute("SELECT label FROM _smoke_test WHERE id = 1").fetchone()
    assert row is not None
    assert row[0] == "hello"
    test_warehouse.execute("DROP TABLE _smoke_test")
