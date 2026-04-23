from app.services.database_service import DatabaseService


class DatabaseToolService:
    def __init__(self, database_service: DatabaseService) -> None:
        self._database_service = database_service

    def tool_definitions(self) -> list[dict[str, object]]:
        return [
            {
                "name": "list_allowed_tables",
                "description": "List the database tables that are exposed to the chatbot.",
                "input_schema": {},
            },
            {
                "name": "describe_table",
                "description": "Describe the columns available on a single exposed table.",
                "input_schema": {
                    "table_name": "string",
                },
            },
            {
                "name": "query_table",
                "description": "Read up to a bounded number of rows from a single exposed table.",
                "input_schema": {
                    "table_name": "string",
                    "columns": "string[] optional",
                    "limit": "integer optional",
                },
            },
        ]

    def list_allowed_tables(self) -> list[str]:
        return self._database_service.allowed_tables()

    def describe_table(self, table_name: str) -> list[dict[str, str | bool]]:
        return self._database_service.describe_table(table_name)

    def query_table(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        return self._database_service.query_table(table_name, columns=columns, limit=limit)
