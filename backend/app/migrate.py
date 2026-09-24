"""SQLite 結構遷移：新增欄位、移除生物辨識相關設定。"""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine


def _columns(engine: Engine, table: str) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return {r[1] for r in rows}


def _add_column(engine: Engine, table: str, column_def: str) -> None:
    with engine.begin() as conn:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_def}"))


def migrate_schema(engine: Engine) -> None:
    # PostgreSQL／非 SQLite：交由 SQLAlchemy create_all；略過 PRAGMA 增量
    url = str(engine.url)
    if not url.startswith("sqlite"):
        return

    # makeup_records 擴充
    if "makeup_records" in _table_names(engine):
        cols = _columns(engine, "makeup_records")
        additions = {
            "store_id": "store_id INTEGER",
            "reason": "reason TEXT",
            "punched_at": "punched_at DATETIME",
            "submitted_at": "submitted_at DATETIME",
            "missing_event": "missing_event VARCHAR(20)",
        }
        for name, ddl in additions.items():
            if name not in cols:
                _add_column(engine, "makeup_records", ddl)

    if "attendance_daily_summary" in _table_names(engine):
        cols = _columns(engine, "attendance_daily_summary")
        for name, ddl in {
            "attendance_status": "attendance_status VARCHAR(40) DEFAULT 'NO_SCHEDULE'",
            "unscheduled_reason": "unscheduled_reason TEXT",
            "no_break_reason": "no_break_reason TEXT",
            "early_leave_reason": "early_leave_reason TEXT",
            "home_store_id": "home_store_id INTEGER",
            "punch_store_id": "punch_store_id INTEGER",
        }.items():
            if name not in cols:
                _add_column(engine, "attendance_daily_summary", ddl)

    if "attendance_events" in _table_names(engine):
        cols = _columns(engine, "attendance_events")
        if "updated_at" not in cols:
            _add_column(engine, "attendance_events", "updated_at DATETIME")

    if "annual_statistics" in _table_names(engine):
        cols = _columns(engine, "annual_statistics")
        for name, ddl in {
            "unscheduled_count": "unscheduled_count INTEGER DEFAULT 0",
            "unscheduled_work_minutes": "unscheduled_work_minutes INTEGER DEFAULT 0",
            "no_break_count": "no_break_count INTEGER DEFAULT 0",
            "early_leave_reason_count": "early_leave_reason_count INTEGER DEFAULT 0",
        }.items():
            if name not in cols:
                _add_column(engine, "annual_statistics", ddl)

    # 移除生物辨識相關欄位（SQLite 3.35+ 支援 DROP COLUMN）
    drops = [
        ("employees", "webauthn_credential_id"),
        ("employees", "webauthn_public_key"),
        ("employees", "webauthn_sign_count"),
        ("attendance_events", "biometrics_ok"),
    ]
    for table, col in drops:
        if table in _table_names(engine) and col in _columns(engine, table):
            try:
                with engine.begin() as conn:
                    conn.execute(text(f"ALTER TABLE {table} DROP COLUMN {col}"))
            except Exception:
                pass

    if "settings" in _table_names(engine):
        with engine.begin() as conn:
            conn.execute(
                text(
                    "DELETE FROM settings WHERE key IN "
                    "('require_biometrics', 'require_gps', 'require_wifi', "
                    "'wifi_verification_mode')"
                )
            )

    # GPS / Wi-Fi 欄位保留於 SQLite（避免 DROP COLUMN 破壞既有資料）；
    # 應用層已停用現場驗證，不再讀寫這些欄位作為打卡條件。


def _table_names(engine: Engine) -> set[str]:
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table'")
        ).fetchall()
    return {r[0] for r in rows}
