from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "airpl_reports",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "app.tasks.periodic",
        "app.tasks.bootstrap",
        "app.tasks.hourly",
        "app.tasks.reports",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
)

celery_app.conf.task_routes = {
    "tasks.generate_hourly_readings": {"queue": "ingestion"},
    "tasks.generate_weekly_report": {"queue": "reports-weekly"},
    "tasks.generate_monthly_report": {"queue": "reports-monthly"},
}

celery_app.conf.beat_schedule = {
    "generate-hourly-readings": {
        "task": "tasks.generate_hourly_readings",
        "schedule": crontab(minute=0),
    },
    "generate-weekly-report": {
        "task": "tasks.generate_weekly_report",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
    "generate-monthly-report": {
        "task": "tasks.generate_monthly_report",
        "schedule": crontab(hour=3, minute=0, day_of_month=1),
    },
}
