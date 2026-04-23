import re
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlparse

import oracledb


TABLE_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLUMN_NAME_PATTERN = TABLE_NAME_PATTERN
MAX_QUERY_LIMIT = 100


@dataclass(frozen=True)
class DatabaseRepository:
    """Repository boundary for database metadata and future query execution.

    This first version deliberately does not execute arbitrary SQL. For an LLM-backed
    service, that safety boundary matters: only explicitly allowed table names should
    ever be exposed to the model or used by generated queries.
    """

    database_url: str
    allowed_tables: list[str]
    oracle_username: str | None = None
    oracle_password: str | None = None

    def list_allowed_tables(self) -> list[str]:
        return list(self.allowed_tables)

    def validate_table_access(self, table_name: str) -> str:
        normalized = table_name.strip()
        if not TABLE_NAME_PATTERN.fullmatch(normalized):
            raise ValueError(f"Invalid table name: {table_name}")
        if normalized not in self.allowed_tables:
            raise ValueError(f"Table is not allowed: {table_name}")
        return normalized

    def validate_requested_tables(self, requested_tables: list[str]) -> list[str]:
        return [self.validate_table_access(table) for table in requested_tables]

    def list_table_columns(self, table_name: str) -> list[dict[str, str | bool]]:
        normalized_table = self.validate_table_access(table_name)
        if self._is_sqlite_url():
            return self._list_sqlite_table_columns(normalized_table)
        if self._is_oracle_jdbc_url():
            return self._list_oracle_table_columns(normalized_table)
        raise ValueError("Schema inspection currently supports Oracle JDBC and sqlite URLs only")

    def query_table(
        self,
        table_name: str,
        columns: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, object]]:
        normalized_table = self.validate_table_access(table_name)
        normalized_limit = self._validate_query_limit(limit)
        available_columns = self.list_table_columns(normalized_table)
        selected_columns = self._resolve_selected_columns(columns, available_columns)
        if self._is_sqlite_url():
            return self._query_sqlite_table(normalized_table, selected_columns, normalized_limit)
        if self._is_oracle_jdbc_url():
            return self._query_oracle_table(normalized_table, selected_columns, normalized_limit)
        raise ValueError("Table queries currently support Oracle JDBC and sqlite URLs only")

    def check_connection(self) -> None:
        if not self._is_oracle_jdbc_url():
            raise ValueError("Database connectivity check currently supports Oracle JDBC URLs only")
        if not self.oracle_username or not self.oracle_password:
            raise ValueError("Oracle username and password are required for connectivity checks")

        host, port, service_name = self._parse_oracle_jdbc_url()
        dsn = oracledb.makedsn(host=host, port=port, service_name=service_name)
        with oracledb.connect(
            user=self.oracle_username,
            password=self.oracle_password,
            dsn=dsn,
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM dual")
                cursor.fetchone()

    def _is_oracle_jdbc_url(self) -> bool:
        return self.database_url.startswith("jdbc:oracle:thin:@")

    def _is_sqlite_url(self) -> bool:
        return self.database_url.startswith("sqlite:///")

    def _parse_oracle_jdbc_url(self) -> tuple[str, int, str]:
        jdbc_prefix = "jdbc:oracle:thin:@"
        target = self.database_url.removeprefix(jdbc_prefix)
        parsed = urlparse(target)
        if not parsed.hostname or not parsed.path:
            raise ValueError(f"Unsupported Oracle JDBC URL: {self.database_url}")
        service_name = parsed.path.lstrip("/")
        if not service_name:
            raise ValueError(f"Unsupported Oracle JDBC URL: {self.database_url}")
        return parsed.hostname, parsed.port or 1521, service_name

    def _parse_sqlite_path(self) -> str:
        return self.database_url.removeprefix("sqlite:///")

    def _validate_query_limit(self, limit: int) -> int:
        if limit < 1 or limit > MAX_QUERY_LIMIT:
            raise ValueError(f"Query limit must be between 1 and {MAX_QUERY_LIMIT}")
        return limit

    def _resolve_selected_columns(
        self,
        columns: list[str] | None,
        available_columns: list[dict[str, str | bool]],
    ) -> list[str]:
        available_column_names = [str(column["name"]) for column in available_columns]
        available_column_name_set = set(available_column_names)
        if not columns:
            return available_column_names

        selected_columns: list[str] = []
        for column_name in columns:
            normalized_column = self._validate_column_name(column_name)
            if normalized_column not in available_column_name_set:
                raise ValueError(f"Column is not available on the table: {column_name}")
            selected_columns.append(normalized_column)
        return selected_columns

    def _validate_column_name(self, column_name: str) -> str:
        normalized = column_name.strip()
        if not COLUMN_NAME_PATTERN.fullmatch(normalized):
            raise ValueError(f"Invalid column name: {column_name}")
        return normalized

    @contextmanager
    def _sqlite_connection(self):
        connection = sqlite3.connect(self._parse_sqlite_path())
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    @contextmanager
    def _oracle_connection(self):
        if not self.oracle_username or not self.oracle_password:
            raise ValueError("Oracle username and password are required for database access")
        host, port, service_name = self._parse_oracle_jdbc_url()
        dsn = oracledb.makedsn(host=host, port=port, service_name=service_name)
        with oracledb.connect(
            user=self.oracle_username,
            password=self.oracle_password,
            dsn=dsn,
        ) as connection:
            yield connection

    def _list_sqlite_table_columns(self, table_name: str) -> list[dict[str, str | bool]]:
        with self._sqlite_connection() as connection:
            rows = connection.execute(f'PRAGMA table_info("{table_name}")').fetchall()
        if not rows:
            raise ValueError(f"Table metadata not found: {table_name}")
        return [
            {
                "name": str(row["name"]),
                "data_type": str(row["type"] or ""),
                "nullable": not bool(row["notnull"]),
            }
            for row in rows
        ]

    def _list_oracle_table_columns(self, table_name: str) -> list[dict[str, str | bool]]:
        with self._oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT column_name, data_type, nullable
                    FROM user_tab_columns
                    WHERE table_name = :table_name
                    ORDER BY column_id
                    """,
                    table_name=table_name.upper(),
                )
                rows = cursor.fetchall()
        if not rows:
            raise ValueError(f"Table metadata not found: {table_name}")
        return [
            {
                "name": str(column_name),
                "data_type": str(data_type),
                "nullable": nullable == "Y",
            }
            for column_name, data_type, nullable in rows
        ]

    def _query_sqlite_table(
        self,
        table_name: str,
        columns: list[str],
        limit: int,
    ) -> list[dict[str, object]]:
        column_sql = ", ".join(f'"{column}"' for column in columns)
        with self._sqlite_connection() as connection:
            rows = connection.execute(
                f'SELECT {column_sql} FROM "{table_name}" LIMIT {limit}'
            ).fetchall()
        return [dict(row) for row in rows]

    def _query_oracle_table(
        self,
        table_name: str,
        columns: list[str],
        limit: int,
    ) -> list[dict[str, object]]:
        column_sql = ", ".join(columns)
        with self._oracle_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT {column_sql} FROM {table_name} FETCH FIRST {limit} ROWS ONLY"
                )
                column_names = [description[0] for description in cursor.description]
                rows = cursor.fetchall()
        return [
            {column_name: value for column_name, value in zip(column_names, row, strict=True)}
            for row in rows
        ]
