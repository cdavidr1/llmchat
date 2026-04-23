from functools import lru_cache
import json
import os
from pathlib import Path
from typing import Annotated, Any

from pydantic import BaseModel, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_CONFIG_DIR = "/vault/secrets"
DEFAULT_ORACLE_SECRET_FILE = "/vault/secrets/oracle.json"
DEFAULT_FALLBACK_CONFIG_DIR = "/app/config.example"


class ConfigLoadInfo(BaseModel):
    source: str
    config_dir: str
    loaded_files: list[str] = Field(default_factory=list)
    fallback_config_dir: str | None = None
    fallback_loaded_files: list[str] = Field(default_factory=list)


class Settings(BaseSettings):
    app_name: str = "llmchat"
    app_env: str = "local"
    log_level: str = "INFO"
    llm_provider: str = "openai"
    llm_model: str = "gpt-4o-mini"
    llm_provider_api_key: SecretStr | None = None
    database_url: str = "sqlite:///./llmchat.db"
    oracle_username: str | None = None
    oracle_password: SecretStr | None = None
    allowed_tables: Annotated[list[str], NoDecode] = Field(default_factory=list)
    config_dir: str = DEFAULT_CONFIG_DIR

    model_config = SettingsConfigDict(env_prefix="LLMCHAT_", extra="ignore")

    @field_validator("allowed_tables", mode="before")
    @classmethod
    def parse_allowed_tables(cls, value: str | list[str] | None) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [table.strip() for table in value.split(",") if table.strip()]
        return value

    @property
    def has_llm_api_key(self) -> bool:
        return self.llm_provider_api_key is not None and bool(
            self.llm_provider_api_key.get_secret_value()
        )


@lru_cache
def get_settings() -> Settings:
    return load_settings_with_info().settings


@lru_cache
def get_config_load_info() -> ConfigLoadInfo:
    return load_settings_with_info().config_load


class LoadedSettings(BaseModel):
    settings: Settings
    config_load: ConfigLoadInfo


def load_settings(config_dir: str | Path | None = None) -> Settings:
    return load_settings_with_info(config_dir).settings


def load_settings_with_info(config_dir: str | Path | None = None) -> LoadedSettings:
    resolved_config_dir = config_dir or os.getenv("LLMCHAT_CONFIG_DIR", DEFAULT_CONFIG_DIR)
    resolved_config_dir_str = str(Path(resolved_config_dir))
    default_oracle_secret_file = (
        DEFAULT_ORACLE_SECRET_FILE
        if resolved_config_dir_str == DEFAULT_CONFIG_DIR
        else str(Path(resolved_config_dir_str) / "oracle.json")
    )
    resolved_oracle_secret_file = os.getenv(
        "SECRET_FILE",
        default_oracle_secret_file,
    )
    config_values, config_load = load_mounted_config(
        resolved_config_dir,
        resolved_oracle_secret_file,
    )
    fallback_config_dir = os.getenv("LLMCHAT_FALLBACK_CONFIG_DIR", DEFAULT_FALLBACK_CONFIG_DIR)
    fallback_config_dir_str = str(Path(fallback_config_dir))
    fallback_enabled = fallback_config_dir_str != resolved_config_dir_str
    fallback_values, fallback_loaded_files = load_fallback_config(
        fallback_config_dir_str if fallback_enabled else None
    )
    merged_values = {
        **fallback_values,
        **config_values,
    }
    merged_values.setdefault("config_dir", resolved_config_dir_str)
    config_load.fallback_config_dir = fallback_config_dir_str if fallback_enabled else None
    config_load.fallback_loaded_files = fallback_loaded_files
    config_load.source = resolve_combined_config_source(
        primary_source=config_load.source,
        fallback_loaded=bool(fallback_loaded_files),
    )
    try:
        settings = Settings(**merged_values)
    except ValidationError:
        settings = Settings(config_dir=str(resolved_config_dir))
        config_load = ConfigLoadInfo(
            source="defaults",
            config_dir=str(resolved_config_dir),
        )
    return LoadedSettings(settings=settings, config_load=config_load)


def load_mounted_config(
    config_dir: str | Path,
    oracle_secret_file: str | Path | None = None,
) -> tuple[dict[str, str], ConfigLoadInfo]:
    """Load sidecar-written configuration from a mounted directory.

    Expected layout is one setting per file, for example:

    /vault/secrets/
      llm_provider
      llm_model
      llm_provider_api_key
      database_url
      allowed_tables
      oracle.json

    Environment variables are intentionally only a fallback/bootstrap layer.
    In Kubernetes, Vault Agent Injector writes these files into `/vault/secrets`.
    """

    path = Path(config_dir)
    values: dict[str, str] = {}
    loaded_files: list[str] = []
    loaded_mounted_files = False
    loaded_oracle_json = False
    oracle_secret_path = Path(oracle_secret_file or path / "oracle.json")

    if path.exists() and path.is_dir():
        for file_path in path.iterdir():
            if not file_path.is_file() or file_path.name.startswith("."):
                continue
            if file_path.name == "oracle.json":
                oracle_values = load_oracle_secret(file_path)
                if oracle_values:
                    for key, value in oracle_values.items():
                        values.setdefault(key, value)
                    loaded_oracle_json = True
                    loaded_files.append(file_path.name)
                continue
            try:
                raw_value = file_path.read_text(encoding="utf-8").strip()
            except OSError:
                continue
            key = file_path.name.lower().replace("-", "_")
            values[key] = raw_value
            loaded_files.append(file_path.name)
            loaded_mounted_files = True

    if oracle_secret_path.is_file() and oracle_secret_path.name not in loaded_files:
        oracle_values = load_oracle_secret(oracle_secret_path)
        if oracle_values:
            values.update(
                {
                    key: value
                    for key, value in oracle_values.items()
                    if key not in values
                }
            )
            loaded_oracle_json = True
            loaded_files.append(oracle_secret_path.name)

    return values, ConfigLoadInfo(
        source=resolve_config_source(loaded_mounted_files, loaded_oracle_json),
        config_dir=str(path),
        loaded_files=sorted(loaded_files),
    )


def load_oracle_secret(secret_file: str | Path) -> dict[str, str]:
    path = Path(secret_file)
    try:
        raw_data: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    if not isinstance(raw_data, dict):
        return {}

    values: dict[str, str] = {}
    database_url = raw_data.get("url")
    if isinstance(database_url, str) and database_url.strip():
        values["database_url"] = database_url.strip()
    oracle_username = raw_data.get("username")
    if isinstance(oracle_username, str) and oracle_username.strip():
        values["oracle_username"] = oracle_username.strip()
    oracle_password = raw_data.get("password")
    if isinstance(oracle_password, str) and oracle_password.strip():
        values["oracle_password"] = oracle_password.strip()
    return values


def load_fallback_config(config_dir: str | Path | None) -> tuple[dict[str, str], list[str]]:
    if config_dir is None:
        return {}, []
    path = Path(config_dir)
    if not path.exists() or not path.is_dir():
        return {}, []

    values: dict[str, str] = {}
    loaded_files: list[str] = []
    for file_path in path.iterdir():
        if not file_path.is_file() or file_path.name.startswith("."):
            continue
        try:
            raw_value = file_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        key = file_path.name.lower().replace("-", "_")
        values[key] = raw_value
        loaded_files.append(file_path.name)
    return values, sorted(loaded_files)


def resolve_config_source(loaded_mounted_files: bool, loaded_oracle_json: bool) -> str:
    if loaded_mounted_files and loaded_oracle_json:
        return "mounted-files+oracle-json"
    if loaded_mounted_files:
        return "mounted-files"
    if loaded_oracle_json:
        return "oracle-json"
    return "defaults"


def resolve_combined_config_source(primary_source: str, fallback_loaded: bool) -> str:
    if fallback_loaded and primary_source == "defaults":
        return "config-example"
    if fallback_loaded:
        return f"{primary_source}+config-example"
    return primary_source
