"""Environment-backed application settings."""

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Mapping


class ConfigurationError(ValueError):
    """Raised when an application setting is invalid or missing."""


@dataclass(frozen=True)
class Settings:
    """Runtime configuration for the resume analyzer."""

    openai_api_key: str | None
    openai_model: str
    max_resume_chars: int
    openai_timeout_seconds: float
    database_path: Path

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "Settings":
        """Create settings from environment variables."""
        env = os.environ if environ is None else environ
        try:
            max_resume_chars = int(env.get("MAX_RESUME_CHARS", "30000"))
            timeout_seconds = float(env.get("OPENAI_TIMEOUT_SECONDS", "45"))
        except ValueError as exc:
            raise ConfigurationError(
                "MAX_RESUME_CHARS and OPENAI_TIMEOUT_SECONDS must be numeric."
            ) from exc

        if max_resume_chars <= 0:
            raise ConfigurationError("MAX_RESUME_CHARS must be greater than zero.")
        if timeout_seconds <= 0:
            raise ConfigurationError("OPENAI_TIMEOUT_SECONDS must be greater than zero.")

        api_key = env.get("OPENAI_API_KEY", "").strip() or None
        return cls(
            openai_api_key=api_key,
            openai_model=env.get("OPENAI_MODEL", "gpt-4o-mini").strip()
            or "gpt-4o-mini",
            max_resume_chars=max_resume_chars,
            openai_timeout_seconds=timeout_seconds,
            database_path=Path(
                env.get("RESUME_ANALYZER_DB_PATH", ".data/analyses.sqlite3")
            ),
        )

    def require_api_key(self) -> str:
        """Return the configured API key or raise a clear configuration error."""
        if not self.openai_api_key:
            raise ConfigurationError(
                "OPENAI_API_KEY is not configured. Add it to your .env file."
            )
        return self.openai_api_key
