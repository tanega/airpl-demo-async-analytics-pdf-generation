from app.db import get_connection
from app.referentiel.build import build_referentiel


def test_build_referentiel_loads_all_communes() -> None:
    count = build_referentiel()
    assert count == 1228

    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM communes WHERE insee_code = ?", ("44050",)
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row["commune_nom"] == "Crossac"
    assert row["dept_code"] == "44"
    assert row["epci_nom"] is not None
    assert row["ptot_2026"] is not None


def test_build_referentiel_is_idempotent() -> None:
    first = build_referentiel()
    second = build_referentiel()
    assert first == second == 1228
