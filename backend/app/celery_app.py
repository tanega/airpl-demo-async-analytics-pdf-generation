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
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Europe/Paris",
    enable_utc=True,
)

celery_app.conf.beat_schedule = {
    "generate-hourly-readings": {
        "task": "tasks.generate_hourly_readings",
        "schedule": crontab(minute=0),
    },
}
