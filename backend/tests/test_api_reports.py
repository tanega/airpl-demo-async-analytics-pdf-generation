from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app import api
from app.main import app
from app.reports_history import record_run

client = TestClient(app)


class _FakeAsyncTask:
    def __init__(self, task_id: str) -> None:
        self.id = task_id


def test_trigger_weekly_report(monkeypatch) -> None:
    monkeypatch.setattr(
        api.reports.generate_weekly_report,
        "delay",
        lambda reference_date=None: _FakeAsyncTask("weekly-task-id"),
    )

    response = client.post("/reports/weekly")

    assert response.status_code == 202
    assert response.json() == {"task_id": "weekly-task-id"}


def test_trigger_monthly_report(monkeypatch) -> None:
    monkeypatch.setattr(
        api.reports.generate_monthly_report,
        "delay",
        lambda reference_date=None: _FakeAsyncTask("monthly-task-id"),
    )

    response = client.post("/reports/monthly")

    assert response.status_code == 202
    assert response.json() == {"task_id": "monthly-task-id"}


class _FakeAsyncResult:
    def __init__(self, status: str, result=None) -> None:
        self.status = status
        self.result = result

    def successful(self) -> bool:
        return self.status == "SUCCESS"

    def failed(self) -> bool:
        return self.status == "FAILURE"


def test_task_status_pending(monkeypatch) -> None:
    monkeypatch.setattr(
        api.reports.celery_app, "AsyncResult", lambda task_id: _FakeAsyncResult("PENDING")
    )

    response = client.get("/reports/tasks/some-id")

    assert response.status_code == 200
    assert response.json() == {
        "task_id": "some-id",
        "status": "PENDING",
        "result": None,
        "error": None,
    }


def test_task_status_success(monkeypatch) -> None:
    monkeypatch.setattr(
        api.reports.celery_app,
        "AsyncResult",
        lambda task_id: _FakeAsyncResult("SUCCESS", result={"storage_location": "s3://x/y.pdf"}),
    )

    response = client.get("/reports/tasks/some-id")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "SUCCESS"
    assert body["result"] == {"storage_location": "s3://x/y.pdf"}


def test_task_status_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        api.reports.celery_app,
        "AsyncResult",
        lambda task_id: _FakeAsyncResult("FAILURE", result=RuntimeError("boom")),
    )

    response = client.get("/reports/tasks/some-id")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "FAILURE"
    assert "boom" in body["error"]


def test_history_returns_recorded_runs() -> None:
    record_run(
        "weekly",
        "2026-07-16",
        "2026-07-22",
        "success",
        datetime.now(timezone.utc),
        1.23,
        storage_location="s3://reports/x.pdf",
        file_size_bytes=42,
    )

    response = client.get("/reports/history")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["report_type"] == "weekly"
    assert body[0]["storage_location"] == "s3://reports/x.pdf"


def test_history_filters_by_report_type() -> None:
    now = datetime.now(timezone.utc)
    record_run("weekly", "2026-07-16", "2026-07-22", "success", now, 1.0, "s3://r/w.pdf", 10)
    record_run("monthly", "2026-07-01", "2026-07-31", "success", now, 2.0, "s3://r/m.pdf", 20)

    response = client.get("/reports/history", params={"report_type": "monthly"})

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["report_type"] == "monthly"


def test_download_link_not_found() -> None:
    response = client.get("/reports/9999/download")
    assert response.status_code == 404


def test_download_link_not_ready() -> None:
    run_id = record_run(
        "weekly",
        "2026-07-16",
        "2026-07-22",
        "failed",
        datetime.now(timezone.utc),
        0.5,
        error_message="boom",
    )

    response = client.get(f"/reports/{run_id}/download")

    assert response.status_code == 409


def test_download_link_success(monkeypatch) -> None:
    run_id = record_run(
        "weekly",
        "2026-07-16",
        "2026-07-22",
        "success",
        datetime.now(timezone.utc),
        1.0,
        storage_location="s3://reports/x.pdf",
        file_size_bytes=42,
    )
    monkeypatch.setattr(
        api.reports, "presigned_url_for", lambda storage_location, **kwargs: "https://fake-url"
    )

    response = client.get(f"/reports/{run_id}/download")

    assert response.status_code == 200
    assert response.json() == {"download_url": "https://fake-url"}
