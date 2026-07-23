from datetime import date

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.celery_app import celery_app
from app.reports_history import get_run, list_runs
from app.storage import presigned_url_for
from app.tasks.reports import generate_monthly_report, generate_weekly_report

router = APIRouter(prefix="/reports", tags=["reports"])


class TaskTriggerResponse(BaseModel):
    task_id: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None
    error: str | None = None


class ReportRun(BaseModel):
    id: int
    report_type: str
    period_start: str
    period_end: str
    status: str
    started_at: str
    duration_seconds: float
    storage_location: str | None
    file_size_bytes: int | None
    error_message: str | None


class DownloadLinkResponse(BaseModel):
    download_url: str


@router.post("/weekly", response_model=TaskTriggerResponse, status_code=202)
def trigger_weekly_report(reference_date: date | None = None) -> TaskTriggerResponse:
    """Déclenche manuellement une génération de rapport hebdomadaire (hors planification)."""
    task = generate_weekly_report.delay(
        reference_date=reference_date.isoformat() if reference_date else None
    )
    return TaskTriggerResponse(task_id=task.id)


@router.post("/monthly", response_model=TaskTriggerResponse, status_code=202)
def trigger_monthly_report(reference_date: date | None = None) -> TaskTriggerResponse:
    """Déclenche manuellement une génération de rapport mensuel (hors planification)."""
    task = generate_monthly_report.delay(
        reference_date=reference_date.isoformat() if reference_date else None
    )
    return TaskTriggerResponse(task_id=task.id)


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """État d'avancement d'une tâche de génération en cours (PENDING/STARTED/SUCCESS/FAILURE)."""
    result = celery_app.AsyncResult(task_id)
    if result.successful():
        return TaskStatusResponse(task_id=task_id, status=result.status, result=result.result)
    if result.failed():
        return TaskStatusResponse(task_id=task_id, status=result.status, error=str(result.result))
    return TaskStatusResponse(task_id=task_id, status=result.status)


@router.get("/history", response_model=list[ReportRun])
def get_history(
    report_type: str | None = Query(default=None, pattern="^(weekly|monthly)$"),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[dict]:
    """Historique des rapports générés (succès et échecs), le plus récent en premier."""
    return list_runs(report_type=report_type, limit=limit)


@router.get("/{run_id}/download", response_model=DownloadLinkResponse)
def get_download_link(run_id: int) -> DownloadLinkResponse:
    """Lien de téléchargement temporaire (URL présignée MinIO/S3) pour un rapport généré."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="report run not found")
    if run["status"] != "success" or not run["storage_location"]:
        raise HTTPException(
            status_code=409, detail=f"report not available (status: {run['status']})"
        )
    return DownloadLinkResponse(download_url=presigned_url_for(run["storage_location"]))
