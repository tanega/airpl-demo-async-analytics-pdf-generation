from app.db import get_connection
from app.referentiel.build import build_referentiel
from app.tasks.hourly import generate_hourly_readings


def test_generate_hourly_readings_for_known_date() -> None:
    build_referentiel()
    # 363 zones dans le CSV ATMO pour cette date, dont 2 sans commune connue
    # dans le référentiel (cf. ROADMAP.md §3.2) -> 361 relevés insérés.
    inserted = generate_hourly_readings(for_date="2026-07-22")
    assert inserted == 361

    conn = get_connection()
    try:
        count = conn.execute("SELECT COUNT(*) FROM hourly_readings").fetchone()[0]
    finally:
        conn.close()
    assert count == 361


def test_generate_hourly_readings_defaults_to_latest_date() -> None:
    build_referentiel()
    inserted = generate_hourly_readings()
    assert inserted == 361


def test_generate_hourly_readings_without_referentiel_skips_everything() -> None:
    inserted = generate_hourly_readings(for_date="2026-07-22")
    assert inserted == 0
