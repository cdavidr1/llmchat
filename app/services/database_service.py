from app.repositories.database import DatabaseRepository


class DatabaseService:
    def __init__(self, repository: DatabaseRepository) -> None:
        self._repository = repository

    @property
    def database_url(self) -> str:
        return self._repository.database_url

    def allowed_tables(self) -> list[str]:
        return self._repository.list_allowed_tables()

    def resolve_requested_tables(self, requested_tables: list[str]) -> list[str]:
        if not requested_tables:
            return []
        return self._repository.validate_requested_tables(requested_tables)

    def check_connection(self) -> None:
        self._repository.check_connection()

    def describe_table(self, table_name: str) -> list[dict[str, str | bool]]:
        return self._repository.list_table_columns(table_name)

    def query_table(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        return self._repository.query_table(table_name, columns=columns, limit=limit)
