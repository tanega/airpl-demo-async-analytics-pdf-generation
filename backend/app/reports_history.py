from datetime import datetime

from app.db import get_connection, init_db


def record_run(
    report_type: str,
    period_start: str,
    period_end: str,
    status: str,
    started_at: datetime,
    duration_seconds: float,
    storage_location: str | None = None,
    file_size_bytes: int | None = None,
    error_message: str | None = None,
) -> int:
    init_db()
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            INSERT INTO report_runs (
                report_type, period_start, period_end, status, started_at,
                duration_seconds, storage_location, file_size_bytes, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_type,
                period_start,
                period_end,
                status,
                started_at.isoformat(),
                duration_seconds,
                storage_location,
                file_size_bytes,
                error_message,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_runs(report_type: str | None = None, limit: int = 50) -> list[dict]:
    init_db()
    conn = get_connection()
    try:
        query = "SELECT * FROM report_runs"
        params: tuple = ()
        if report_type:
            query += " WHERE report_type = ?"
            params = (report_type,)
        query += " ORDER BY started_at DESC LIMIT ?"
        params = (*params, limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def get_run(run_id: int) -> dict | None:
    init_db()
    conn = get_connection()
    try:
        row = conn.execute("SELECT * FROM report_runs WHERE id = ?", (run_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()
