import sqlite3
from pathlib import Path

from app.core.config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS communes (
    insee_code TEXT PRIMARY KEY,
    commune_nom TEXT NOT NULL,
    dept_code TEXT NOT NULL,
    dept_nom TEXT NOT NULL,
    region_code TEXT NOT NULL,
    region_nom TEXT NOT NULL,
    epci_code TEXT,
    epci_nom TEXT,
    arrondissement_code TEXT,
    arrondissement_nom TEXT,
    siren_code TEXT,
    nature_juridique TEXT,
    mode_financ TEXT,
    nb_membres INTEGER,
    ptot_2026 INTEGER,
    pmun_2026 INTEGER
);

CREATE TABLE IF NOT EXISTS hourly_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insee_code TEXT NOT NULL REFERENCES communes(insee_code),
    qualificatif TEXT NOT NULL,
    qualificatif_score INTEGER NOT NULL,
    source_date TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_hourly_readings_insee_recorded
    ON hourly_readings (insee_code, recorded_at);

CREATE TABLE IF NOT EXISTS report_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_type TEXT NOT NULL,
    period_start TEXT NOT NULL,
    period_end TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    file_path TEXT,
    file_size_bytes INTEGER,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_report_runs_type_started
    ON report_runs (report_type, started_at);
"""


def get_connection() -> sqlite3.Connection:
    db_path = Path(get_settings().db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
