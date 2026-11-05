"""Resume analysis service backed by the OpenAI API."""

import json
import logging
from typing import Any, TypedDict

from openai import APIError, OpenAI

from app.config.settings import ConfigurationError, Settings
from app.prompts.resume_prompt import SYSTEM_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)


class JobRecommendation(TypedDict):
    """A suggested role and its resume-based rationale."""

    title: str
    fit_reason: str


class ResumeAnalysis(TypedDict):
    """Validated shape of the generated analysis."""

    summary: str
    technical_skills: list[str]
    soft_skills: list[str]
    experience_assessment: str
    job_recommendations: list[JobRecommendation]
    missing_skills: list[str]
    learning_suggestions: list[str]
    resume_improvements: list[str]


class ResumeValidationError(ValueError):
    """Raised when resume input is invalid."""


class AnalysisError(RuntimeError):
    """Raised when the model cannot return a valid analysis."""


class ResumeAnalyzer:
    """Validate resumes and request structured feedback from OpenAI."""

    def __init__(self, settings: Settings, client: Any | None = None) -> None:
        self.settings = settings
        self._client = client

    def analyze(self, resume_text: str) -> ResumeAnalysis:
        """Analyze resume text and return a validated result."""
        self._validate_resume(resume_text)
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
                    {"role": "user", "content": build_user_prompt(resume_text)},
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

    @staticmethod
    def _validate_analysis(payload: Any) -> ResumeAnalysis:
        if not isinstance(payload, dict):
            raise ValueError("Analysis must be a JSON object.")

        string_fields = ("summary", "experience_assessment")
        list_fields = (
            "technical_skills",
            "soft_skills",
            "missing_skills",
            "learning_suggestions",
            "resume_improvements",
        )
        for field in string_fields:
            if not isinstance(payload.get(field), str) or not payload[field].strip():
                raise ValueError(f"{field} must be a non-empty string.")
        for field in list_fields:
            values = payload.get(field)
            if not isinstance(values, list) or not all(
                isinstance(value, str) and value.strip() for value in values
            ):
                raise ValueError(f"{field} must be a list of non-empty strings.")

        recommendations = payload.get("job_recommendations")
        if not isinstance(recommendations, list):
            raise ValueError("job_recommendations must be a list.")
        validated_recommendations: list[JobRecommendation] = []
        for item in recommendations:
            if (
                not isinstance(item, dict)
                or not isinstance(item.get("title"), str)
                or not item["title"].strip()
                or not isinstance(item.get("fit_reason"), str)
                or not item["fit_reason"].strip()
            ):
                raise ValueError("Each job recommendation needs a title and fit_reason.")
            validated_recommendations.append(
                {"title": item["title"].strip(), "fit_reason": item["fit_reason"].strip()}
            )

        return {
            "summary": payload["summary"].strip(),
            "technical_skills": [value.strip() for value in payload["technical_skills"]],
            "soft_skills": [value.strip() for value in payload["soft_skills"]],
            "experience_assessment": payload["experience_assessment"].strip(),
            "job_recommendations": validated_recommendations,
            "missing_skills": [value.strip() for value in payload["missing_skills"]],
            "learning_suggestions": [
                value.strip() for value in payload["learning_suggestions"]
            ],
            "resume_improvements": [
                value.strip() for value in payload["resume_improvements"]
            ],
        }
