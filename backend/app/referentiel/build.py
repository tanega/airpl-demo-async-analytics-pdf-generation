import csv
import json
from pathlib import Path

from app.core.config import get_settings
from app.db import get_connection, init_db


def _geojson_path() -> Path:
    return Path(get_settings().data_dir) / "geo" / "communes_pays_de_la_loire.geojson"


def _epci_csv_path() -> Path:
    return Path(get_settings().data_dir) / "geo" / "epci_communes_pays_de_la_loire.csv"


_EPCI_DEFAULTS = {
    "nature_juridique": None,
    "mode_financ": None,
    "nb_membres": None,
    "ptot_2026": None,
    "pmun_2026": None,
}


def _load_communes_attributes() -> dict[str, dict]:
    with _geojson_path().open(encoding="utf-8") as f:
        geojson = json.load(f)

    communes = {}
    for feature in geojson["features"]:
        props = feature["properties"]
        communes[props["insee_code"]] = {
            "insee_code": props["insee_code"],
            "commune_nom": props["commune_nom"],
            "dept_code": props["dept_code"],
            "dept_nom": props["dept_nom"],
            "region_code": props["region_code"],
            "region_nom": props["region_nom"],
            "epci_code": props.get("epci_code"),
            "epci_nom": props.get("epci_nom"),
            "arrondissement_code": props.get("arrondissement_code"),
            "arrondissement_nom": props.get("arrondissement_nom"),
            "siren_code": props.get("siren_code"),
            **_EPCI_DEFAULTS,
        }
    return communes


def _enrich_with_epci_population(communes: dict[str, dict]) -> None:
    with _epci_csv_path().open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter=";")
        for row in reader:
            commune = communes.get(row["insee"])
            if commune is None:
                continue
            commune["nature_juridique"] = row["nature_juridique"]
            commune["mode_financ"] = row["mode_financ"]
            commune["nb_membres"] = int(row["nb_membres"])
            commune["ptot_2026"] = int(row["ptot_2026"])
            commune["pmun_2026"] = int(row["pmun_2026"])


def build_referentiel() -> int:
    """Matérialise le référentiel communal (géo + admin + population EPCI) en base.

    Combine `communes_pays_de_la_loire.geojson` (§3.2) et
    `epci_communes_pays_de_la_loire.csv` (§3.3, DGCL) sur `insee_code`/`insee`.
    Idempotent (upsert) : à ré-exécuter si les fichiers sources changent, appelé
    automatiquement au démarrage des workers (cf. `app/tasks/bootstrap.py`).
    Ne couvre que les communes de la région Pays de la Loire.
    """
    communes = _load_communes_attributes()
    _enrich_with_epci_population(communes)

    init_db()
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT INTO communes (
                insee_code, commune_nom, dept_code, dept_nom, region_code, region_nom,
                epci_code, epci_nom, arrondissement_code, arrondissement_nom, siren_code,
                nature_juridique, mode_financ, nb_membres, ptot_2026, pmun_2026
            ) VALUES (
                :insee_code, :commune_nom, :dept_code, :dept_nom, :region_code, :region_nom,
                :epci_code, :epci_nom, :arrondissement_code, :arrondissement_nom, :siren_code,
                :nature_juridique, :mode_financ, :nb_membres, :ptot_2026, :pmun_2026
            )
            ON CONFLICT (insee_code) DO UPDATE SET
                commune_nom = excluded.commune_nom,
                dept_code = excluded.dept_code,
                dept_nom = excluded.dept_nom,
                region_code = excluded.region_code,
                region_nom = excluded.region_nom,
                epci_code = excluded.epci_code,
                epci_nom = excluded.epci_nom,
                arrondissement_code = excluded.arrondissement_code,
                arrondissement_nom = excluded.arrondissement_nom,
                siren_code = excluded.siren_code,
                nature_juridique = excluded.nature_juridique,
                mode_financ = excluded.mode_financ,
                nb_membres = excluded.nb_membres,
                ptot_2026 = excluded.ptot_2026,
                pmun_2026 = excluded.pmun_2026
            """,
            list(communes.values()),
        )
        conn.commit()
        return len(communes)
    finally:
        conn.close()
