"""Tests for opt-in local report storage."""

from pathlib import Path

from app.services.report_repository import ReportRepository


def test_repository_saves_lists_and_deletes_reports(tmp_path: Path) -> None:
    repository = ReportRepository(tmp_path / "nested" / "reports.sqlite3")
    repository.initialize()
    report_id = repository.save({"summary": "A sample report"})

    reports = repository.list_recent()
    assert len(reports) == 1
    assert reports[0].id == report_id
    assert reports[0].analysis == {"summary": "A sample report"}

    repository.delete(report_id)
    assert repository.list_recent() == []
