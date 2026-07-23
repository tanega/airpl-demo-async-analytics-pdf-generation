from celery.signals import worker_ready

from app.referentiel.build import build_referentiel


@worker_ready.connect
def bootstrap_referentiel(**kwargs) -> None:
    build_referentiel()
