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
    "overall_ats_score": 78,
    "summary": "Early-career Python developer.",
    "scoring_breakdown": {
        "keyword_match_score": 82,
        "experience_relevance_score": 75,
        "formatting_score": 77,
    },
    "keyword_analysis": {
        "matched_keywords": ["Python", "FastAPI"],
        "missing_keywords": ["pytest"],
        "critical_skills_gap": ["Automated testing"],
    },
    "bullet_improvements": [
        {
            "original_bullet": "Developed APIs for e-commerce systems.",
            "suggested_bullet": (
                "Developed APIs for e-commerce systems, improving [add verified "
                "metric] through [describe the work performed]."
            ),
            "reasoning": "Add verified impact metrics without inventing results.",
        }
    ],
    "actionable_recommendations": ["Add verified outcomes to project bullets."],
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


def test_analyze_includes_optional_job_description_as_untrusted_data() -> None:
    client, completions = make_client(json.dumps(VALID_ANALYSIS))
    ResumeAnalyzer(make_settings(), client=client).analyze(
        "Python developer", "Must know Python and pytest."
    )

    assert completions.request is not None
    prompt = completions.request["messages"][1]["content"]
    assert "<job_description>" in prompt
    assert "Must know Python and pytest." in prompt
    assert "<candidate_resume>" in prompt


def test_analyze_uses_general_audit_when_job_description_is_missing() -> None:
    client, completions = make_client(json.dumps(VALID_ANALYSIS))
    ResumeAnalyzer(make_settings(), client=client).analyze("Python developer")

    assert completions.request is not None
    assert "Perform a general technical resume audit." in (
        completions.request["messages"][1]["content"]
    )


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


def test_analyze_rejects_job_description_over_configured_limit() -> None:
    client, _ = make_client(json.dumps(VALID_ANALYSIS))
    with pytest.raises(ResumeValidationError, match="Job description"):
        ResumeAnalyzer(make_settings(max_chars=10), client=client).analyze(
            "Resume", "A job description that is too long."
        )


def test_analyze_rejects_malformed_model_json() -> None:
    client, _ = make_client("not json")
    with pytest.raises(AnalysisError, match="invalid response"):
        ResumeAnalyzer(make_settings(), client=client).analyze("Resume text")


def test_analyze_rejects_incomplete_model_response() -> None:
    client, _ = make_client(json.dumps({"summary": "Incomplete"}))
    with pytest.raises(AnalysisError, match="invalid response"):
        ResumeAnalyzer(make_settings(), client=client).analyze("Resume text")


@pytest.mark.parametrize("score", [-1, 101, True, "80"])
def test_analyze_rejects_invalid_scores(score: Any) -> None:
    invalid_analysis = json.loads(json.dumps(VALID_ANALYSIS))
    invalid_analysis["overall_ats_score"] = score
    client, _ = make_client(json.dumps(invalid_analysis))

    with pytest.raises(AnalysisError, match="invalid response"):
        ResumeAnalyzer(make_settings(), client=client).analyze("Resume text")


def test_missing_api_key_fails_before_network_request() -> None:
    with pytest.raises(ConfigurationError, match="OPENAI_API_KEY"):
        ResumeAnalyzer(make_settings()).analyze("Resume text")
