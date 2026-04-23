import pytest

from app.repositories.database import DatabaseRepository
from app.services.database_service import DatabaseService


def test_database_service_resolves_allowed_tables() -> None:
    repository = DatabaseRepository(
        database_url="sqlite:///./test.db",
        allowed_tables=["customers", "orders"],
    )
    service = DatabaseService(repository)

    assert service.database_url == "sqlite:///./test.db"
    assert service.allowed_tables() == ["customers", "orders"]
    assert service.resolve_requested_tables(["customers"]) == ["customers"]


def test_database_service_rejects_invalid_or_unallowed_tables() -> None:
    repository = DatabaseRepository(database_url="sqlite:///./test.db", allowed_tables=["customers"])
    service = DatabaseService(repository)

    with pytest.raises(ValueError, match="Invalid table name"):
        service.resolve_requested_tables(["customers; drop table customers"])

    with pytest.raises(ValueError, match="Table is not allowed"):
        service.resolve_requested_tables(["orders"])


def test_database_service_parses_oracle_jdbc_url() -> None:
    repository = DatabaseRepository(
        database_url="jdbc:oracle:thin:@//oracle-host:1521/FREEPDB1",
        allowed_tables=[],
        oracle_username="appuser",
        oracle_password="secret",
    )

    assert repository._parse_oracle_jdbc_url() == ("oracle-host", 1521, "FREEPDB1")


def test_database_service_rejects_connectivity_check_without_oracle_credentials() -> None:
    repository = DatabaseRepository(
        database_url="jdbc:oracle:thin:@//oracle-host:1521/FREEPDB1",
        allowed_tables=[],
    )

    with pytest.raises(ValueError, match="Oracle username and password are required"):
        repository.check_connection()
