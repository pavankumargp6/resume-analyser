"""Deterministic tests for resume analysis without an API connection."""

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.config.settings import ConfigurationError, Settings
from app.services.resume_service import (
    AnalysisError,
    ResumeAnalyzer,
    ResumeValidationError,
)


VALID_ANALYSIS = {
    "summary": "Early-career Python developer.",
    "technical_skills": ["Python", "FastAPI"],
    "soft_skills": ["Communication"],
    "experience_assessment": "Two years of backend experience are described.",
    "job_recommendations": [
        {
            "title": "Junior Backend Developer",
            "fit_reason": "The resume describes Python API development.",
        }
    ],
    "missing_skills": ["Automated testing"],
    "learning_suggestions": ["Build a project with pytest."],
    "resume_improvements": ["Add measurable outcomes to project bullets."],
}


class FakeCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.request: dict[str, Any] | None = None

    def create(self, **kwargs: Any) -> SimpleNamespace:
        self.request = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(message=SimpleNamespace(content=self.content))
            ]
        )


def make_settings(max_chars: int = 30000) -> Settings:
    return Settings(
        openai_api_key=None,
        openai_model="test-model",
        max_resume_chars=max_chars,
        openai_timeout_seconds=10,
        database_path=Path(":memory:"),
    )


def make_client(content: str) -> tuple[SimpleNamespace, FakeCompletions]:
    completions = FakeCompletions(content)
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=completions)
    )
    return client, completions


def test_analyze_returns_validated_result_and_structured_request() -> None:
    client, completions = make_client(json.dumps(VALID_ANALYSIS))
    result = ResumeAnalyzer(make_settings(), client=client).analyze(
        "Python developer with two years of experience."
    )

    assert result == VALID_ANALYSIS
    assert completions.request is not None
    assert completions.request["response_format"] == {"type": "json_object"}
    assert "Python developer" in completions.request["messages"][1]["content"]


@pytest.mark.parametrize("resume", ["", "  ", None])
def test_analyze_rejects_empty_or_non_text_input(resume: Any) -> None:
    client, _ = make_client(json.dumps(VALID_ANALYSIS))
    with pytest.raises(ResumeValidationError):
        ResumeAnalyzer(make_settings(), client=client).analyze(resume)


def test_analyze_rejects_input_over_configured_limit() -> None:
    client, _ = make_client(json.dumps(VALID_ANALYSIS))
    with pytest.raises(ResumeValidationError, match="10 characters"):
        ResumeAnalyzer(make_settings(max_chars=10), client=client).analyze(
            "This resume is too long."
        )


def test_analyze_rejects_malformed_model_json() -> None:
    client, _ = make_client("not json")
    with pytest.raises(AnalysisError, match="invalid response"):
        ResumeAnalyzer(make_settings(), client=client).analyze("Resume text")


def test_analyze_rejects_incomplete_model_response() -> None:
    client, _ = make_client(json.dumps({"summary": "Incomplete"}))
    with pytest.raises(AnalysisError, match="invalid response"):
        ResumeAnalyzer(make_settings(), client=client).analyze("Resume text")


def test_missing_api_key_fails_before_network_request() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        ResumeAnalyzer(make_settings()).analyze("Resume text")
