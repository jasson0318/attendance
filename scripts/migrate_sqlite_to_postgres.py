"""
SQLite → PostgreSQL 安全遷移工具。

絕對不修改／刪除來源 SQLite。

用法：
  python scripts/migrate_sqlite_to_postgres.py --dry-run
  python scripts/migrate_sqlite_to_postgres.py --confirm

環境：
  SQLITE_URL   預設 sqlite:///D:/出勤打卡系統/data/attendance.sqlite3（唯讀開啟）
  DATABASE_URL 或 POSTGRES_URL：目標 PostgreSQL（僅 --confirm 時寫入）

流程：
  1. 讀取 SQLite 各表
  2. dry-run：只印 row count／checksum，不寫 PG
  3. confirm：Alembic／create_all 確保 schema → 依依賴順序複製 → sync sequences → verify
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_SQLITE = ROOT / "data" / "attendance.sqlite3"

# 依 FK 依賴順序（來源 → 目標）
TABLE_ORDER = [
    "stores",
    "employees",
    "settings",
    "schedules",
    "attendance_events",
    "makeup_records",
    "unscheduled_attendances",
    "attendance_daily_summary",
    "annual_statistics",
    "audit_logs",
    "revoked_tokens",
    "token_activities",
    "excel_preview_blobs",
]

CHECKSUM_TABLES = [
    "employees",
    "schedules",
    "attendance_events",
    "makeup_records",
]


def _sqlite_url(path: Path) -> str:
    # 唯讀 URI，避免誤寫來源
    posix = path.resolve().as_posix()
    return f"sqlite:///file:{posix}?mode=ro&uri=true"


def _jsonable(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (datetime, date, time)):
        return v.isoformat()
    if isinstance(v, bytes):
        return hashlib.sha256(v).hexdigest()
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, bool):
        return v
    return v


def _row_dict(keys: Iterable[str], row: Any) -> dict[str, Any]:
    return {k: _jsonable(row._mapping[k]) for k in keys}


def table_exists(engine: Engine, name: str) -> bool:
    return name in inspect(engine).get_table_names()


def row_count(engine: Engine, table: str) -> int:
    if not table_exists(engine, table):
        return -1
    with engine.connect() as conn:
        return int(conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() or 0)


def fetch_all(engine: Engine, table: str) -> tuple[list[str], list[dict[str, Any]]]:
    if not table_exists(engine, table):
        return [], []
    with engine.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table}"))
        keys = list(result.keys())
        rows = [_row_dict(keys, r) for r in result]
    # 穩定排序：優先 id，否則整列 JSON
    if "id" in keys:
        rows.sort(key=lambda r: (r.get("id") is None, r.get("id") or 0))
    elif "cache_key" in keys:
        rows.sort(key=lambda r: str(r.get("cache_key") or ""))
    else:
        rows.sort(key=lambda r: json.dumps(r, sort_keys=True, ensure_ascii=False))
    return keys, rows


def checksum_table(engine: Engine, table: str) -> str:
    keys, rows = fetch_all(engine, table)
    payload = json.dumps({"keys": keys, "rows": rows}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def ensure_postgres_schema(pg_url: str) -> Engine:
    """對空／既有 PG 建立完整 schema（metadata + alembic stamp 可選）。"""
    os.environ.setdefault("DATABASE_URL", pg_url)
    from backend.app.database import Base
    from backend.app import models  # noqa: F401
    from backend.app.services import preview_store  # noqa: F401

    engine = create_engine(pg_url, pool_pre_ping=True)
    Base.metadata.create_all(bind=engine)
    return engine


def copy_table(src: Engine, dst: Engine, table: str, *, dry_run: bool) -> int:
    if not table_exists(src, table):
        print(f"  skip {table}: not in SQLite")
        return 0
    keys, rows = fetch_all(src, table)
    print(f"  {table}: {len(rows)} rows")
    if dry_run or not rows:
        return len(rows)

    # 清空目標表（僅遷移工具在 confirm 時；保留來源 SQLite）
    with dst.begin() as conn:
        conn.execute(text(f"DELETE FROM {table}"))

    cols = ", ".join(keys)
    placeholders = ", ".join(f":{k}" for k in keys)
    sql = text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})")

    # 還原原始型別給 SQLAlchemy（iso 字串對 DateTime 通常可接受；bytes 需還原）
    raw_keys, raw_rows = [], []
    with src.connect() as conn:
        result = conn.execute(text(f"SELECT * FROM {table}"))
        raw_keys = list(result.keys())
        raw_rows = [dict(r._mapping) for r in result]

    with dst.begin() as conn:
        for row in raw_rows:
            conn.execute(sql, row)
    return len(raw_rows)


def sync_sequences(engine: Engine) -> None:
    """PostgreSQL：將 SERIAL／IDENTITY sequence 對齊 MAX(id)。"""
    if not str(engine.url).startswith("postgresql"):
        return
    tables = inspect(engine).get_table_names()
    with engine.begin() as conn:
        for table in tables:
            cols = {c["name"] for c in inspect(engine).get_columns(table)}
            if "id" not in cols:
                continue
            # setval(pg_get_serial_sequence(...), max)
            seq_sql = text(
                "SELECT pg_get_serial_sequence(:tbl, 'id')"
            )
            seq = conn.execute(seq_sql, {"tbl": table}).scalar()
            if not seq:
                continue
            max_id = conn.execute(text(f'SELECT MAX(id) FROM "{table}"')).scalar()
            if max_id is None:
                continue
            conn.execute(text("SELECT setval(:seq, :m)"), {"seq": seq, "m": int(max_id)})
            print(f"  sequence {seq} -> {max_id}")


def verify(src: Engine, dst: Engine) -> bool:
    ok = True
    print("\n=== Row counts ===")
    for table in TABLE_ORDER:
        sc = row_count(src, table)
        dc = row_count(dst, table)
        status = "PASS" if sc == dc or (sc < 0 and dc < 0) else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  {table}: sqlite={sc} postgres={dc} [{status}]")

    print("\n=== Checksums ===")
    for table in CHECKSUM_TABLES:
        if not table_exists(src, table):
            continue
        sc = checksum_table(src, table)
        dc = checksum_table(dst, table)
        status = "PASS" if sc == dc else "FAIL"
        if status == "FAIL":
            ok = False
        print(f"  {table}: {status}")
        print(f"    sqlite={sc}")
        print(f"    postgres={dc}")

    print("\n=== Sample (employees / stores) ===")
    for table in ("stores", "employees"):
        if not table_exists(src, table):
            continue
        _, srows = fetch_all(src, table)
        _, drows = fetch_all(dst, table)
        match = srows == drows
        if not match:
            ok = False
        print(f"  {table} full compare: {'PASS' if match else 'FAIL'} (n={len(srows)})")

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate SQLite → PostgreSQL (safe)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--dry-run", action="store_true", help="只驗證／列印，不寫 PostgreSQL")
    group.add_argument("--confirm", action="store_true", help="正式寫入 PostgreSQL")
    parser.add_argument(
        "--sqlite",
        type=Path,
        default=Path(os.environ.get("SQLITE_PATH", str(DEFAULT_SQLITE))),
        help="來源 SQLite 路徑（唯讀）",
    )
    parser.add_argument(
        "--postgres-url",
        default=os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL") or "",
        help="目標 PostgreSQL URL（confirm 必填）",
    )
    args = parser.parse_args()

    sqlite_path: Path = args.sqlite
    if not sqlite_path.exists():
        print(f"ERROR: SQLite 不存在: {sqlite_path}")
        return 2

    src = create_engine(_sqlite_url(sqlite_path), connect_args={"uri": True})

    print(f"Source SQLite (read-only): {sqlite_path}")
    print(f"Mode: {'DRY-RUN' if args.dry_run else 'CONFIRM WRITE'}")

    if args.dry_run:
        print("\n=== SQLite inventory ===")
        for table in TABLE_ORDER:
            c = row_count(src, table)
            if c >= 0:
                print(f"  {table}: {c}")
        print("\n=== SQLite checksums ===")
        for table in CHECKSUM_TABLES:
            if table_exists(src, table):
                print(f"  {table}: {checksum_table(src, table)}")

        pg_url = (args.postgres_url or "").strip()
        if not pg_url or pg_url.startswith("sqlite"):
            print(
                "\n[DRY-RUN] 未提供可用 PostgreSQL URL — "
                "migration tool / checksum 就緒，等待真正 PostgreSQL。"
            )
            print("NOT claiming migration success.")
            return 0

        print("\n[DRY-RUN] 連線 PostgreSQL 比對（不寫入）…")
        dst = create_engine(pg_url, pool_pre_ping=True)
        ok = verify(src, dst)
        return 0 if ok else 1

    # --confirm
    pg_url = (args.postgres_url or "").strip()
    if not pg_url or pg_url.startswith("sqlite"):
        print(
            "ERROR: --confirm 需要 PostgreSQL URL（--postgres-url 或環境變數 "
            "POSTGRES_URL / DATABASE_URL）。不會猜測連線字串。"
        )
        return 2

    print("Ensuring PostgreSQL schema…")
    dst = ensure_postgres_schema(pg_url)

    print("Copying tables…")
    for table in TABLE_ORDER:
        copy_table(src, dst, table, dry_run=False)

    print("Syncing sequences…")
    sync_sequences(dst)

    print("Verifying…")
    ok = verify(src, dst)
    if ok:
        print("\nMIGRATION VERIFIED: row counts + checksums PASS")
        return 0
    print("\nMIGRATION FAILED verification — PostgreSQL 資料請人工檢查；來源 SQLite 未改動。")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
