import shutil
import subprocess
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from app.celery_app import celery_app
from app.reports_history import record_run

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
TEMPLATE_PATH = BACKEND_DIR / "reports" / "report_template.qmd"
REPORTS_DIR = BACKEND_DIR / "var" / "reports"


def _weekly_period(reference: date) -> tuple[date, date]:
    end = reference - timedelta(days=1)
    start = end - timedelta(days=6)
    return start, end


def _monthly_period(reference: date) -> tuple[date, date]:
    first_of_month = reference.replace(day=1)
    if first_of_month.month == 12:
        next_month = first_of_month.replace(year=first_of_month.year + 1, month=1)
    else:
        next_month = first_of_month.replace(month=first_of_month.month + 1)
    return first_of_month, next_month - timedelta(days=1)


def _render(start: date, end: date, output_name: str) -> str:
    """Rend le template et déplace le PDF dans REPORTS_DIR.

    `--output` de quarto n'accepte qu'un nom de fichier, pas un chemin
    (il lande à côté du .qmd) ; `--output-dir` a un comportement erratique
    quand ce dossier partage un segment de nom avec celui du document
    (ici `reports/`). On rend donc à côté du .qmd puis on déplace — avec
    `shutil.move` plutôt qu'un `rename` : `reports/` et `var/reports/` sont
    deux volumes Docker distincts, un rename direct échoue en cross-device.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            "quarto",
            "render",
            str(TEMPLATE_PATH),
            "--to",
            "typst",
            "-P",
            f"start_date:{start.isoformat()}",
            "-P",
            f"end_date:{end.isoformat()}",
            "--output",
            output_name,
        ],
        cwd=TEMPLATE_PATH.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    output_path = REPORTS_DIR / output_name
    shutil.move(str(TEMPLATE_PATH.parent / output_name), str(output_path))
    return str(output_path)


def _generate_report(report_type: str, start: date, end: date, output_name: str) -> dict:
    """Rend le rapport et enregistre sa traçabilité (statut, durée, taille, chemin — §6 ROADMAP.md).

    Un échec de rendu est à la fois consigné dans `report_runs` (status="failed",
    `error_message`) et propagé, pour que Celery reflète aussi l'échec de la tâche.
    """
    started_at = datetime.now(timezone.utc)
    t0 = time.monotonic()
    try:
        output_path = _render(start, end, output_name)
    except subprocess.CalledProcessError as exc:
        record_run(
            report_type,
            start.isoformat(),
            end.isoformat(),
            "failed",
            started_at,
            time.monotonic() - t0,
            error_message=(exc.stderr or str(exc))[-2000:],
        )
        raise

    record_run(
        report_type,
        start.isoformat(),
        end.isoformat(),
        "success",
        started_at,
        time.monotonic() - t0,
        file_path=output_path,
    )
    return {
        "period": report_type,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "output_path": output_path,
    }


@celery_app.task(name="tasks.generate_weekly_report")
def generate_weekly_report(reference_date: str | None = None) -> dict:
    """Rapport hebdomadaire : agrégation des 7 derniers jours complets (§2 ROADMAP.md)."""
    reference = date.fromisoformat(reference_date) if reference_date else date.today()
    start, end = _weekly_period(reference)
    output_name = f"rapport_hebdomadaire_{start.isoformat()}_{end.isoformat()}.pdf"
    return _generate_report("weekly", start, end, output_name)


@celery_app.task(name="tasks.generate_monthly_report")
def generate_monthly_report(reference_date: str | None = None) -> dict:
    """Rapport mensuel : agrégation du mois courant, équivalent aux 4 périodes
    hebdomadaires du mois (§2 ROADMAP.md) — même template, période élargie."""
    reference = date.fromisoformat(reference_date) if reference_date else date.today()
    start, end = _monthly_period(reference)
    output_name = f"rapport_mensuel_{start.strftime('%Y-%m')}.pdf"
    return _generate_report("monthly", start, end, output_name)
