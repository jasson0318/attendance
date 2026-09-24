"""正式部署前檢查（只回報，不修改系統設定／防火牆／網路）。"""
from __future__ import annotations

import importlib
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    CHECKS.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


def port_listening(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            return s.connect_ex(("127.0.0.1", port)) == 0
        except OSError:
            return False


def main() -> int:
    print("=" * 40)
    print("出勤打卡系統 — Preflight Check")
    print(f"專案根目錄: {ROOT}")
    print("=" * 40)

    py_ver = sys.version_info
    check(
        "python",
        py_ver.major == 3 and py_ver.minor >= 12,
        f"{sys.version.split()[0]} (需要 3.12+)",
    )

    try:
        import pip  # noqa: F401

        check("pip", True, getattr(pip, "__version__", "ok"))
    except Exception as ex:  # noqa: BLE001
        check("pip", False, str(ex))

    req = ROOT / "requirements.txt"
    check("requirements.txt", req.exists(), str(req))

    required_files = [
        "run.py",
        "pytest.ini",
        "README.md",
        "backend/app/main.py",
        "backend/app/config.py",
        "backend/app/migrate.py",
        "backend/app/seed.py",
        "backend/app/database.py",
        "frontend/index.html",
        "frontend/admin.html",
        "frontend/static/js/app.js",
        "frontend/static/js/admin.js",
        "frontend/static/js/auth_session.js",
        "frontend/static/css/app.css",
        "scripts/start_production.bat",
        "scripts/stop_production.bat",
        "scripts/install_requirements.bat",
    ]
    missing = [p for p in required_files if not (ROOT / p).exists()]
    check("required_project_files", not missing, "缺: " + ", ".join(missing) if missing else "ok")

    data_dir = ROOT / "data"
    if data_dir.exists():
        check("data_dir_exists", True, str(data_dir))
    else:
        check(
            "data_dir_exists",
            True,
            "目前尚無 data\\（首次啟動會自動建立；部署副本應含 data\\.gitkeep）",
        )

    sqlite_path = data_dir / "attendance.sqlite3"
    secret_path = data_dir / ".secret_key"
    check(
        "sqlite_policy",
        True,
        "正式機不沿用開發 SQLite；現況: " + ("有檔（部署時勿複製到正式機）" if sqlite_path.exists() else "無"),
    )
    check(
        "secret_key_file_policy",
        True,
        "正式機不沿用開發 .secret_key；現況: " + ("有檔（部署時勿複製到正式機）" if secret_path.exists() else "無"),
    )

    packages = [
        "fastapi",
        "uvicorn",
        "sqlalchemy",
        "passlib",
        "jose",
        "openpyxl",
        "httpx",
        "pydantic",
        "pytest",
    ]
    missing_pkgs = []
    for name in packages:
        try:
            importlib.import_module(name if name != "jose" else "jose")
        except Exception:  # noqa: BLE001
            missing_pkgs.append(name)
    check(
        "python_packages",
        not missing_pkgs,
        "缺套件: " + ", ".join(missing_pkgs) if missing_pkgs else "ok",
    )

    # SECRET_KEY 設計（不印出真正密鑰）
    sys.path.insert(0, str(ROOT))
    try:
        from backend.app import config as cfg

        has_env = bool((__import__("os").environ.get("ATTENDANCE_SECRET_KEY") or "").strip())
        has_file = (cfg.DATA_DIR / ".secret_key").exists()
        hardcoded = cfg.SECRET_KEY == "attendance-system-change-me-in-production-2026"
        check("secret_key_not_hardcoded_default", not hardcoded, "ok" if not hardcoded else "仍為舊預設字串")
        check(
            "secret_key_source_design",
            True,
            "優先 ATTENDANCE_SECRET_KEY 環境變數，否則 data\\.secret_key（可自動建立且會沿用）"
            + (f"；目前: {'環境變數' if has_env else ('檔案' if has_file else '尚未建立（啟動時會產生）')}"),
        )
        check("bind_host_port", cfg.HOST == "0.0.0.0" and cfg.PORT == 8800, f"{cfg.HOST}:{cfg.PORT}")
    except Exception as ex:  # noqa: BLE001
        check("config_import", False, str(ex))

    # FastAPI app import
    try:
        from backend.app.main import app

        check("fastapi_import", app is not None, getattr(app, "title", "ok"))
    except Exception as ex:  # noqa: BLE001
        check("fastapi_import", False, str(ex))

    # 路徑不應硬編碼開發機（粗檢查）
    bad_abs = []
    for rel in ("backend/app/config.py", "run.py", "backend/app/main.py"):
        text = (ROOT / rel).read_text(encoding="utf-8", errors="ignore")
        if "D:\\出勤打卡系統" in text or "D:/出勤打卡系統" in text:
            bad_abs.append(rel)
    check("no_hardcoded_dev_path_in_core", not bad_abs, ", ".join(bad_abs) if bad_abs else "ok")

    listening = port_listening(8800)
    check(
        "port_8800_status",
        True,
        "目前有行程在聽 :8800（若要重啟請先 stop_production.bat）"
        if listening
        else "目前 :8800 空閒（可啟動）",
    )

    # SmartRx 依賴不應存在
    smart_hits = []
    for p in (ROOT / "backend").rglob("*.py"):
        t = p.read_text(encoding="utf-8", errors="ignore").lower()
        if "smartrx" in t:
            smart_hits.append(str(p.relative_to(ROOT)))
    check("no_smartrx_dependency", not smart_hits, ", ".join(smart_hits) if smart_hits else "ok")

    print("-" * 40)
    fatal = [n for n, ok, _ in CHECKS if not ok]
    if fatal:
        print(f"結果: FAIL（{len(fatal)} 項需處理）")
        for n in fatal:
            print(f"  - {n}")
        print("本腳本不會自動修改防火牆／網路／安裝 Python。")
        return 1

    print("結果: ALL CHECKS OK（可進行正式部署準備）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
