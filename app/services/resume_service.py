"""Resume analysis service backed by the OpenAI API."""

import json
import logging
import math
from typing import Any, TypedDict

from openai import APIError, OpenAI

from app.config.settings import ConfigurationError, Settings
from app.prompts.resume_prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class ScoringBreakdown(TypedDict):
    """ATS score components."""

    keyword_match_score: int | float
    experience_relevance_score: int | float
    formatting_score: int | float


class KeywordAnalysis(TypedDict):
    """Keywords identified from the resume and job description."""

    matched_keywords: list[str]
    missing_keywords: list[str]
    critical_skills_gap: list[str]


class BulletImprovement(TypedDict):
    """A resume bullet suggestion that preserves candidate-provided facts."""

    original_bullet: str
    suggested_bullet: str
    reasoning: str


class ResumeAnalysis(TypedDict):
    """Validated shape of the generated analysis."""

    overall_ats_score: int | float
    summary: str
    scoring_breakdown: ScoringBreakdown
    keyword_analysis: KeywordAnalysis
    bullet_improvements: list[BulletImprovement]
    actionable_recommendations: list[str]


class ResumeValidationError(ValueError):
    """Raised when resume input is invalid."""


class AnalysisError(RuntimeError):
    """Raised when the model cannot return a valid analysis."""


class ResumeAnalyzer:
    """Validate resumes and request structured feedback from OpenAI."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client

    def analyze(
        self, resume_text: str, job_description: str = ""
    ) -> ResumeAnalysis:
        """Analyze resume text and return a validated result."""
        self._validate_resume(resume_text)
        self._validate_job_description(job_description)
        if self._client is None:
            api_key = self.settings.require_api_key()
            self._client = OpenAI(
                api_key=api_key,
                timeout=self.settings.openai_timeout_seconds,
            )

        try:
            response = self._client.chat.completions.create(
                model=self.settings.openai_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": build_user_prompt(resume_text, job_description),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except APIError as exc:
            logger.warning("OpenAI request failed (%s).", type(exc).__name__)
            raise AnalysisError(
                "The AI provider could not complete the analysis. Please try again."
            ) from exc

        try:
            content = response.choices[0].message.content
            if not isinstance(content, str) or not content.strip():
                raise ValueError("The model returned an empty response.")
            payload = json.loads(content)
            return self._validate_analysis(payload)
        except (AttributeError, IndexError, KeyError, TypeError, ValueError) as exc:
            logger.warning("The AI provider returned an invalid analysis response.")
            raise AnalysisError(
                "The AI provider returned an invalid response. Please try again."
            ) from exc

    def _validate_resume(self, resume_text: str) -> None:
        if not isinstance(resume_text, str) or not resume_text.strip():
            raise ResumeValidationError("Enter resume text before analyzing.")
        if len(resume_text) > self.settings.max_resume_chars:
            raise ResumeValidationError(
                f"Resume text must be {self.settings.max_resume_chars:,} "
                "characters or fewer."
            )

    def _validate_job_description(self, job_description: str) -> None:
        if not isinstance(job_description, str):
            raise ResumeValidationError("Job description must be text.")
        if len(job_description) > self.settings.max_resume_chars:
            raise ResumeValidationError(
                f"Job description must be {self.settings.max_resume_chars:,} "
                "characters or fewer."
            )

    @staticmethod
    def _validate_analysis(payload: Any) -> ResumeAnalysis:
        if not isinstance(payload, dict):
            raise ValueError("Analysis must be a JSON object.")

        overall_score = ResumeAnalyzer._validate_score(
            payload.get("overall_ats_score"), "overall_ats_score"
        )
        summary = ResumeAnalyzer._validate_non_empty_string(
            payload.get("summary"), "summary"
        )
        breakdown = payload.get("scoring_breakdown")
        if not isinstance(breakdown, dict):
            raise ValueError("scoring_breakdown must be an object.")
        validated_breakdown: ScoringBreakdown = {
            "keyword_match_score": ResumeAnalyzer._validate_score(
                breakdown.get("keyword_match_score"),
                "keyword_match_score",
            ),
            "experience_relevance_score": ResumeAnalyzer._validate_score(
                breakdown.get("experience_relevance_score"),
                "experience_relevance_score",
            ),
            "formatting_score": ResumeAnalyzer._validate_score(
                breakdown.get("formatting_score"), "formatting_score"
            ),
        }

        keyword_analysis = payload.get("keyword_analysis")
        if not isinstance(keyword_analysis, dict):
            raise ValueError("keyword_analysis must be an object.")
        validated_keywords: KeywordAnalysis = {
            "matched_keywords": ResumeAnalyzer._validate_string_list(
                keyword_analysis.get("matched_keywords"), "matched_keywords"
            ),
            "missing_keywords": ResumeAnalyzer._validate_string_list(
                keyword_analysis.get("missing_keywords"), "missing_keywords"
            ),
            "critical_skills_gap": ResumeAnalyzer._validate_string_list(
                keyword_analysis.get("critical_skills_gap"), "critical_skills_gap"
            ),
        }

        bullets = payload.get("bullet_improvements")
        if not isinstance(bullets, list):
            raise ValueError("bullet_improvements must be a list.")
        validated_bullets: list[BulletImprovement] = []
        for item in bullets:
            if not isinstance(item, dict):
                raise ValueError("Each bullet improvement must be an object.")
            validated_bullets.append(
                {
                    "original_bullet": ResumeAnalyzer._validate_non_empty_string(
                        item.get("original_bullet"), "original_bullet"
                    ),
                    "suggested_bullet": ResumeAnalyzer._validate_non_empty_string(
                        item.get("suggested_bullet"), "suggested_bullet"
                    ),
                    "reasoning": ResumeAnalyzer._validate_non_empty_string(
                        item.get("reasoning"), "reasoning"
                    ),
                }
            )
        return {
            "overall_ats_score": overall_score,
            "summary": summary,
            "scoring_breakdown": validated_breakdown,
            "keyword_analysis": validated_keywords,
            "bullet_improvements": validated_bullets,
            "actionable_recommendations": ResumeAnalyzer._validate_string_list(
                payload.get("actionable_recommendations"),
                "actionable_recommendations",
            ),
        }

    @staticmethod
    def _validate_score(value: Any, field: str) -> int | float:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or not 0 <= value <= 100
        ):
            raise ValueError(f"{field} must be a number from 0 to 100.")
        return value

    @staticmethod
    def _validate_non_empty_string(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string.")
        return value.strip()

    @staticmethod
    def _validate_string_list(value: Any, field: str) -> list[str]:
        if not isinstance(value, list):
            raise ValueError(f"{field} must be a list.")
        return [
            ResumeAnalyzer._validate_non_empty_string(item, field) for item in value
        ]
