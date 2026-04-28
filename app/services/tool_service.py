from typing import Protocol


class ToolService(Protocol):
    def tool_definitions(self) -> list[dict[str, object]]:
        ...

    def list_allowed_tables(self) -> list[str]:
        ...

    def describe_table(self, table_name: str) -> list[dict[str, str | bool]]:
        ...

    def query_table(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 20,
    ) -> list[dict[str, object]]:
        ...
