import sqlite3

import pytest
from fastapi import HTTPException

from app.api.routes import describe_table, list_allowed_tables, query_table, tool_definitions
from app.core.config import get_settings
from app.schemas.tool import QueryTableRequest


def _create_sqlite_test_db(database_path: str) -> None:
    connection = sqlite3.connect(database_path)
    try:
        connection.execute(
            """
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                city TEXT
            )
            """
        )
        connection.executemany(
            "INSERT INTO customers (name, city) VALUES (?, ?)",
            [
                ("Ada", "London"),
                ("Grace", "New York"),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def _write_sqlite_config(config_dir, database_path: str) -> None:
    config_dir.mkdir()
    (config_dir / "database_url").write_text(f"sqlite:///{database_path}", encoding="utf-8")
    (config_dir / "allowed_tables").write_text("customers", encoding="utf-8")
    (config_dir / "app_name").write_text("tool-test", encoding="utf-8")


def test_tool_definitions_are_exposed() -> None:
    response = tool_definitions()

    assert [tool.name for tool in response] == [
        "list_allowed_tables",
        "describe_table",
        "query_table",
    ]


def test_list_allowed_tables_reads_from_config(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "tool-test.db"
    _create_sqlite_test_db(str(database_path))
    config_dir = tmp_path / "config"
    _write_sqlite_config(config_dir, str(database_path))
    missing_fallback = tmp_path / "missing-fallback"
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(missing_fallback))
    get_settings.cache_clear()

    response = list_allowed_tables()

    assert response.tables == ["customers"]


def test_describe_table_returns_sqlite_columns(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "tool-test.db"
    _create_sqlite_test_db(str(database_path))
    config_dir = tmp_path / "config"
    _write_sqlite_config(config_dir, str(database_path))
    missing_fallback = tmp_path / "missing-fallback"
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(missing_fallback))
    get_settings.cache_clear()

    response = describe_table("customers")

    assert response.table_name == "customers"
    assert [column.name for column in response.columns] == ["id", "name", "city"]


def test_query_table_returns_bounded_rows(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "tool-test.db"
    _create_sqlite_test_db(str(database_path))
    config_dir = tmp_path / "config"
    _write_sqlite_config(config_dir, str(database_path))
    missing_fallback = tmp_path / "missing-fallback"
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(missing_fallback))
    get_settings.cache_clear()

    response = query_table(QueryTableRequest(table_name="customers", columns=["name"], limit=1))

    assert response.table_name == "customers"
    assert response.columns == ["name"]
    assert response.row_count == 1
    assert response.rows == [{"name": "Ada"}]


def test_query_table_rejects_unavailable_column(monkeypatch, tmp_path) -> None:
    database_path = tmp_path / "tool-test.db"
    _create_sqlite_test_db(str(database_path))
    config_dir = tmp_path / "config"
    _write_sqlite_config(config_dir, str(database_path))
    missing_fallback = tmp_path / "missing-fallback"
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(missing_fallback))
    get_settings.cache_clear()

    with pytest.raises(HTTPException) as exc_info:
        query_table(QueryTableRequest(table_name="customers", columns=["secret_note"], limit=1))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Column is not available on the table: secret_note"
