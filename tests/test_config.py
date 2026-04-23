from app.core.config import load_mounted_config, load_settings, load_settings_with_info


def test_load_mounted_config_reads_one_setting_per_file(tmp_path) -> None:
    (tmp_path / "llm-provider").write_text("anthropic\n", encoding="utf-8")
    (tmp_path / "llm_model").write_text("claude-test", encoding="utf-8")
    (tmp_path / "allowed_tables").write_text("customers, orders", encoding="utf-8")
    (tmp_path / ".ignored").write_text("secret", encoding="utf-8")
    (tmp_path / "nested").mkdir()

    values, config_load = load_mounted_config(tmp_path)

    assert values == {
        "llm_provider": "anthropic",
        "llm_model": "claude-test",
        "allowed_tables": "customers, orders",
    }
    assert config_load.source == "mounted-files"
    assert config_load.loaded_files == ["allowed_tables", "llm-provider", "llm_model"]


def test_load_settings_uses_mounted_config_values(tmp_path) -> None:
    (tmp_path / "app_name").write_text("tribal-chat", encoding="utf-8")
    (tmp_path / "llm_provider_api_key").write_text("vault-key", encoding="utf-8")
    (tmp_path / "database_url").write_text("postgresql://example/db", encoding="utf-8")
    (tmp_path / "allowed_tables").write_text("customers,orders", encoding="utf-8")

    settings = load_settings(tmp_path)

    assert settings.app_name == "tribal-chat"
    assert settings.database_url == "postgresql://example/db"
    assert settings.allowed_tables == ["customers", "orders"]
    assert settings.has_llm_api_key is True


def test_load_settings_can_discover_config_dir_from_environment(tmp_path, monkeypatch) -> None:
    (tmp_path / "llm_provider").write_text("openai-compatible", encoding="utf-8")
    monkeypatch.setenv("LLMCHAT_CONFIG_DIR", str(tmp_path))

    settings = load_settings()

    assert settings.config_dir == str(tmp_path)
    assert settings.llm_provider == "openai-compatible"


def test_load_mounted_config_supports_oracle_json(tmp_path) -> None:
    (tmp_path / "oracle.json").write_text(
        '{"url":"oracle://example/service","username":"app","password":"secret"}',
        encoding="utf-8",
    )

    values, config_load = load_mounted_config(tmp_path)

    assert values["database_url"] == "oracle://example/service"
    assert values["oracle_username"] == "app"
    assert values["oracle_password"] == "secret"
    assert config_load.source == "oracle-json"
    assert config_load.loaded_files == ["oracle.json"]


def test_load_settings_uses_defaults_when_config_path_is_invalid(tmp_path) -> None:
    config_file = tmp_path / "not-a-directory"
    config_file.write_text("broken", encoding="utf-8")

    settings_with_info = load_settings_with_info(config_file)

    assert settings_with_info.settings.app_name == "llmchat"
    assert settings_with_info.settings.config_dir == str(config_file)
    assert settings_with_info.config_load.source == "defaults"
    assert settings_with_info.config_load.loaded_files == []


def test_load_settings_uses_config_example_as_fallback(tmp_path, monkeypatch) -> None:
    fallback_dir = tmp_path / "config.example"
    fallback_dir.mkdir()
    (fallback_dir / "app_name").write_text("fallback-app", encoding="utf-8")
    (fallback_dir / "llm_provider").write_text("anthropic", encoding="utf-8")
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(fallback_dir))

    settings_with_info = load_settings_with_info(tmp_path / "missing")

    assert settings_with_info.settings.app_name == "fallback-app"
    assert settings_with_info.settings.llm_provider == "anthropic"
    assert settings_with_info.config_load.source == "config-example"
    assert settings_with_info.config_load.fallback_loaded_files == ["app_name", "llm_provider"]


def test_load_settings_prefers_mounted_files_over_oracle_json(tmp_path) -> None:
    (tmp_path / "database_url").write_text("postgresql://preferred/db", encoding="utf-8")
    (tmp_path / "oracle.json").write_text(
        '{"url":"oracle://fallback/service","username":"app","password":"secret"}',
        encoding="utf-8",
    )

    settings_with_info = load_settings_with_info(tmp_path)

    assert settings_with_info.settings.database_url == "postgresql://preferred/db"
    assert settings_with_info.config_load.source == "mounted-files+oracle-json"


def test_load_settings_uses_vault_first_and_config_example_for_missing_values(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / "oracle.json").write_text('{"url":"oracle://example/service"}', encoding="utf-8")
    fallback_dir = tmp_path / "config.example"
    fallback_dir.mkdir()
    (fallback_dir / "app_name").write_text("fallback-app", encoding="utf-8")
    (fallback_dir / "llm_provider").write_text("openai-compatible", encoding="utf-8")
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(fallback_dir))

    settings_with_info = load_settings_with_info(tmp_path)

    assert settings_with_info.settings.database_url == "oracle://example/service"
    assert settings_with_info.settings.app_name == "fallback-app"
    assert settings_with_info.settings.llm_provider == "openai-compatible"
    assert settings_with_info.config_load.source == "oracle-json+config-example"
    assert settings_with_info.config_load.loaded_files == ["oracle.json"]
    assert settings_with_info.config_load.fallback_loaded_files == ["app_name", "llm_provider"]


def test_load_settings_does_not_double_count_when_fallback_matches_primary(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / "database_url").write_text("jdbc:oracle:thin:@//127.0.0.1:1521/XEPDB1", encoding="utf-8")
    (tmp_path / "oracle_username").write_text("appuser", encoding="utf-8")
    (tmp_path / "oracle_password").write_text("secret", encoding="utf-8")
    monkeypatch.setenv("LLMCHAT_FALLBACK_CONFIG_DIR", str(tmp_path))

    settings_with_info = load_settings_with_info(tmp_path)

    assert settings_with_info.config_load.source == "mounted-files"
    assert settings_with_info.config_load.fallback_config_dir is None
    assert settings_with_info.config_load.fallback_loaded_files == []


def test_load_settings_can_use_explicit_secret_file_when_config_dir_is_invalid(
    tmp_path,
    monkeypatch,
) -> None:
    config_file = tmp_path / "not-a-directory"
    config_file.write_text("broken", encoding="utf-8")
    secret_file = tmp_path / "oracle.json"
    secret_file.write_text('{"url":"oracle://example/service"}', encoding="utf-8")
    monkeypatch.setenv("SECRET_FILE", str(secret_file))

    settings_with_info = load_settings_with_info(config_file)

    assert settings_with_info.settings.database_url == "oracle://example/service"
    assert settings_with_info.config_load.source == "oracle-json"
    assert settings_with_info.config_load.loaded_files == ["oracle.json"]
