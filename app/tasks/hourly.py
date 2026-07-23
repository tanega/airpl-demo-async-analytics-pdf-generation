import csv
import random
from datetime import datetime, timezone
from pathlib import Path

from app.celery_app import celery_app
from app.db import get_connection, init_db

ATMO_CSV_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "indice_ATMO_2026-1-1_2026-7-22_commune.csv"
)

QUALIFICATIF_SCORES = {
    "bon": 1,
    "moyen": 2,
    "dégradé": 3,
    "mauvais": 4,
    "très mauvais": 5,
    "extrêmement mauvais": 6,
}
SCORE_QUALIFICATIFS = {score: label for label, score in QUALIFICATIF_SCORES.items()}


def _load_rows_for_date(target_date: str) -> list[dict[str, str]]:
    with ATMO_CSV_PATH.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return [row for row in reader if row["date"] == target_date]


def _latest_available_date() -> str:
    with ATMO_CSV_PATH.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f, delimiter=";")
        return max(row["date"] for row in reader)


@celery_app.task(name="tasks.generate_hourly_readings")
def generate_hourly_readings(for_date: str | None = None) -> int:
    """Simule un relevé horaire à partir du CSV ATMO quotidien (§3.1 ROADMAP.md).

    La source ne fournit qu'une valeur par commune et par jour ; ce job simule
    une granularité horaire en bruitant l'indice ordinal autour de la valeur du
    jour, pour donner au pipeline une volumétrie horaire réaliste à agréger
    (Épic 4). `for_date` par défaut = dernière date disponible dans le CSV.
    """
    target_date = for_date or _latest_available_date()
    rows = _load_rows_for_date(target_date)
    if not rows:
        return 0

    init_db()
    conn = get_connection()
    try:
        # Certains code_zone du CSV ATMO n'ont pas de commune correspondante
        # dans le référentiel (communes renumérotées, cf. ROADMAP.md §3.2) —
        # on les ignore plutôt que de faire échouer tout le batch sur la FK.
        known_codes = {r["insee_code"] for r in conn.execute("SELECT insee_code FROM communes")}

        now = datetime.now(timezone.utc).isoformat()
        readings = []
        for row in rows:
            if row["code_zone"] not in known_codes:
                continue
            base_score = QUALIFICATIF_SCORES[row["qualificatif"]]
            noisy_score = max(1, min(6, base_score + random.choice([-1, 0, 0, 0, 1])))
            readings.append(
                {
                    "insee_code": row["code_zone"],
                    "qualificatif": SCORE_QUALIFICATIFS[noisy_score],
                    "qualificatif_score": noisy_score,
                    "source_date": target_date,
                    "recorded_at": now,
                }
            )
        if not readings:
            return 0

        conn.executemany(
            """
            INSERT INTO hourly_readings (
                insee_code, qualificatif, qualificatif_score, source_date, recorded_at, simulated
            ) VALUES (
                :insee_code, :qualificatif, :qualificatif_score, :source_date, :recorded_at, 1
            )
            """,
            readings,
        )
        conn.commit()
        return len(readings)
    finally:
        conn.close()
