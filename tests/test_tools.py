import pytest
from fastapi import HTTPException

from app.api.routes import describe_table, list_allowed_tables, query_table, tool_definitions
from app.schemas.tool import QueryTableRequest


class FakeToolService:
    def tool_definitions(self) -> list[dict[str, object]]:
        return [
            {
                "name": "list_allowed_tables",
                "description": "List allowed tables",
                "input_schema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "describe_table",
                "description": "Describe one table",
                "input_schema": {
                    "type": "object",
                    "properties": {"table_name": {"type": "string"}},
                    "required": ["table_name"],
                },
            },
            {
                "name": "query_table",
                "description": "Query one table",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "table_name": {"type": "string"},
                        "columns": {"type": "array"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["table_name"],
                },
            },
        ]

    def list_allowed_tables(self) -> list[str]:
        return ["customers"]

    def describe_table(self, table_name: str) -> list[dict[str, str | bool]]:
        if table_name != "customers":
            raise ValueError(f"Table is not allowed: {table_name}")
        return [
            {"name": "id", "data_type": "INTEGER", "nullable": False},
            {"name": "name", "data_type": "TEXT", "nullable": False},
            {"name": "city", "data_type": "TEXT", "nullable": True},
        ]

    def query_table_result(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 20,
    ) -> dict[str, object]:
        if table_name != "customers":
            raise ValueError(f"Table is not allowed: {table_name}")
        if columns == ["secret_note"]:
            raise ValueError("Column is not available on the table: secret_note")
        resolved_columns = columns or ["id", "name", "city"]
        rows = [{"name": "Ada"}] if columns == ["name"] and limit == 1 else [
            {"id": 1, "name": "Ada", "city": "London"},
            {"id": 2, "name": "Grace", "city": "New York"},
        ][:limit]
        return {
            "table_name": table_name,
            "columns": resolved_columns,
            "row_count": len(rows),
            "limit_applied": limit,
            "rows": rows,
        }


@pytest.fixture(autouse=True)
def patch_tool_service(monkeypatch):
    monkeypatch.setattr("app.api.routes.build_tool_service", lambda: FakeToolService())


def test_tool_definitions_are_exposed() -> None:
    response = tool_definitions()

    assert [tool.name for tool in response] == [
        "list_allowed_tables",
        "describe_table",
        "query_table",
    ]


def test_list_allowed_tables_reads_from_mcp_service() -> None:
    response = list_allowed_tables()

    assert response.tables == ["customers"]


def test_describe_table_returns_columns_from_mcp_service() -> None:
    response = describe_table("customers")

    assert response.table_name == "customers"
    assert [column.name for column in response.columns] == ["id", "name", "city"]


def test_query_table_returns_bounded_rows() -> None:
    response = query_table(QueryTableRequest(table_name="customers", columns=["name"], limit=1))

    assert response.table_name == "customers"
    assert response.columns == ["name"]
    assert response.row_count == 1
    assert response.rows == [{"name": "Ada"}]


def test_query_table_rejects_unavailable_column() -> None:
    with pytest.raises(HTTPException) as exc_info:
        query_table(QueryTableRequest(table_name="customers", columns=["secret_note"], limit=1))

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Column is not available on the table: secret_note"
