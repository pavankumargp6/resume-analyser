"""Tests for environment-backed settings."""

import pytest

from app.config.settings import ConfigurationError, Settings


def test_settings_read_environment_values() -> None:
    settings = Settings.from_env(
        {
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
            "MAX_RESUME_CHARS": "1200",
            "OPENAI_TIMEOUT_SECONDS": "12.5",
            "RESUME_ANALYZER_DB_PATH": "reports.sqlite3",
        }
    )

    assert settings.openai_api_key == "test-key"
    assert settings.openai_model == "test-model"
    assert settings.max_resume_chars == 1200
    assert settings.openai_timeout_seconds == 12.5
    assert str(settings.database_path) == "reports.sqlite3"


def test_missing_api_key_is_reported() -> None:
    settings = Settings.from_env({})

    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        settings.require_api_key()


@pytest.mark.parametrize(
    "values",
    [
        {"MAX_RESUME_CHARS": "0"},
        {"OPENAI_TIMEOUT_SECONDS": "-1"},
        {"MAX_RESUME_CHARS": "not-a-number"},
    ],
)
def test_invalid_numeric_settings_are_reported(values: dict[str, str]) -> None:
    with pytest.raises(ConfigurationError):
        Settings.from_env(values)
