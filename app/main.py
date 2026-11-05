"""Streamlit user interface for the AI Resume Analyzer."""

import json
import logging
import sqlite3

from dotenv import load_dotenv
import streamlit as st

from app.config.settings import ConfigurationError, Settings
from app.services.report_repository import ReportRepository
from app.services.resume_service import (
    AnalysisError,
    ResumeAnalyzer,
    ResumeValidationError,
)
from app.utils.logging_config import configure_logging


def _render_analysis(analysis: dict[str, object]) -> None:
    st.subheader("ATS Summary")
    st.write(analysis["summary"])
    st.metric("Overall ATS score", f"{analysis['overall_ats_score']}/100")

    st.subheader("Scoring Breakdown")
    score_columns = st.columns(3)
    for column, (label, score) in zip(
        score_columns, analysis["scoring_breakdown"].items()
    ):
        column.metric(label.replace("_", " ").title(), f"{score}/100")

    st.subheader("Keyword Analysis")
    keyword_columns = st.columns(3)
    for column, (label, key) in zip(
        keyword_columns,
        (
            ("Matched Keywords", "matched_keywords"),
            ("Missing Keywords", "missing_keywords"),
            ("Critical Skills Gaps", "critical_skills_gap"),
        ),
    ):
        with column:
            st.markdown(f"**{label}**")
            values = analysis["keyword_analysis"][key]
            st.markdown("\n".join(f"- {item}" for item in values) or "None identified.")

    st.subheader("Bullet Improvements")
    for bullet in analysis["bullet_improvements"]:
        with st.container(border=True):
            st.markdown(f"**Original:** {bullet['original_bullet']}")
            st.markdown(f"**Suggested:** {bullet['suggested_bullet']}")
            st.caption(bullet["reasoning"])

    st.subheader("Actionable Recommendations")
    st.markdown(
        "\n".join(
            f"- {item}" for item in analysis["actionable_recommendations"]
        )
        or "No additional recommendations."
    )

    report_json = json.dumps(analysis, indent=2, ensure_ascii=False)
    st.download_button(
        "Download analysis (JSON)",
        data=report_json,
        file_name="resume-analysis.json",
        mime="application/json",
    )


def main() -> None:
    """Run the Streamlit application."""
    load_dotenv()
    configure_logging()
    settings = Settings.from_env()
    repository = ReportRepository(settings.database_path)

    st.set_page_config(page_title="AI Resume Analyzer", page_icon="📄")
    st.title("AI Resume Analyzer")
    st.write("Get an ATS-focused resume review and identify practical next steps.")
    st.info(
        "Your resume is sent to the configured AI provider for analysis. "
        "It is not saved by this app unless you choose to save the generated "
        "report locally."
    )

    with st.form("resume_form"):
        resume_text = st.text_area(
            "Paste your resume text",
            height=280,
            max_chars=settings.max_resume_chars,
            placeholder="Paste resume content here...",
        )
        job_description = st.text_area(
            "Job description (optional)",
            height=180,
            max_chars=settings.max_resume_chars,
            placeholder="Paste a target job description for a tailored keyword match...",
        )
        save_report = st.checkbox(
            "Save the generated report on this device (the report may contain "
            "personal information).",
            value=False,
        )
        submitted = st.form_submit_button("Analyze resume", type="primary")

    if submitted:
        try:
            analysis = ResumeAnalyzer(settings).analyze(resume_text, job_description)
            st.session_state["latest_analysis"] = analysis
            if save_report:
                repository.initialize()
                repository.save(analysis)
                st.success("Analysis complete. Report saved locally.")
            else:
                st.success("Analysis complete.")
        except (ConfigurationError, ResumeValidationError, AnalysisError) as exc:
            st.error(str(exc))
        except (OSError, sqlite3.Error):
            logging.getLogger(__name__).exception("Could not save the local report.")
            st.error("The report could not be saved to this device.")

    analysis = st.session_state.get("latest_analysis")
    if analysis:
        _render_analysis(analysis)

    with st.expander("Saved reports on this device"):
        try:
            repository.initialize()
            saved_reports = repository.list_recent()
            if not saved_reports:
                st.caption("No reports have been saved.")
            for report in saved_reports:
                st.markdown(f"**Saved {report.created_at}**")
                st.write(report.analysis.get("summary", ""))
                if st.button("Delete report", key=f"delete_{report.id}"):
                    repository.delete(report.id)
                    st.rerun()
        except (OSError, sqlite3.Error):
            logging.getLogger(__name__).exception("Could not access local reports.")
            st.error("Saved reports could not be accessed.")


if __name__ == "__main__":
    main()
