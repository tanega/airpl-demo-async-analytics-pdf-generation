import subprocess
from datetime import date

import pytest

from app.reports_history import list_runs
from app.tasks import reports
from app.tasks.reports import _monthly_period, _weekly_period


def test_weekly_period_covers_seven_full_days_ending_yesterday() -> None:
    start, end = _weekly_period(date(2026, 7, 23))
    assert end == date(2026, 7, 22)
    assert start == date(2026, 7, 16)
    assert (end - start).days == 6


def test_monthly_period_covers_full_month() -> None:
    start, end = _monthly_period(date(2026, 7, 23))
    assert start == date(2026, 7, 1)
    assert end == date(2026, 7, 31)


def test_monthly_period_handles_december_year_rollover() -> None:
    start, end = _monthly_period(date(2026, 12, 15))
    assert start == date(2026, 12, 1)
    assert end == date(2026, 12, 31)


def test_monthly_period_handles_february() -> None:
    start, end = _monthly_period(date(2026, 2, 10))
    assert start == date(2026, 2, 1)
    assert end == date(2026, 2, 28)


def test_generate_report_records_success(monkeypatch, tmp_path) -> None:
    pdf_path = tmp_path / "rapport.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake report")
    monkeypatch.setattr(reports, "_render", lambda start, end, output_name: str(pdf_path))

    result = reports._generate_report("weekly", date(2026, 7, 16), date(2026, 7, 22), "x.pdf")

    assert result["output_path"] == str(pdf_path)
    runs = list_runs("weekly")
    assert len(runs) == 1
    assert runs[0]["status"] == "success"
    assert runs[0]["period_start"] == "2026-07-16"
    assert runs[0]["period_end"] == "2026-07-22"
    assert runs[0]["file_path"] == str(pdf_path)
    assert runs[0]["file_size_bytes"] == pdf_path.stat().st_size
    assert runs[0]["duration_seconds"] >= 0
    assert runs[0]["error_message"] is None


def test_generate_report_records_failure_and_reraises(monkeypatch) -> None:
    def failing_render(start, end, output_name):
        raise subprocess.CalledProcessError(1, ["quarto"], stderr="boom")

    monkeypatch.setattr(reports, "_render", failing_render)

    with pytest.raises(subprocess.CalledProcessError):
        reports._generate_report("weekly", date(2026, 7, 16), date(2026, 7, 22), "x.pdf")

    runs = list_runs("weekly")
    assert len(runs) == 1
    assert runs[0]["status"] == "failed"
    assert runs[0]["file_path"] is None
    assert "boom" in runs[0]["error_message"]
