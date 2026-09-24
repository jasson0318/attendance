"""簡單驗證清單：啟動健康檢查與核心 API。"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from backend.app.main import app

CHECKS = []


def check(name: str, ok: bool, detail: str = ""):
    CHECKS.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name} {detail}")


def main():
    client = TestClient(app)
    r = client.get("/api/health")
    check("runtime_health", r.status_code == 200 and r.json().get("status") == "ok")

    r = client.get("/")
    check("gui_index", r.status_code == 200 and "出勤打卡系統" in r.text)

    r = client.get("/admin")
    check("gui_admin", r.status_code == 200 and "管理後台" in r.text)

    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    check("admin_login", r.status_code == 200 and "access_token" in (r.json() or {}))
    token = r.json().get("access_token") if r.status_code == 200 else None

    if token:
        h = {"Authorization": f"Bearer {token}"}
        d = client.get("/api/dashboard", headers=h)
        check("dashboard", d.status_code == 200)
        s = client.get("/api/settings", headers=h)
        check("settings", s.status_code == 200)
        st = client.get("/api/stores", headers=h)
        check("stores", st.status_code == 200 and len(st.json()) >= 4)

    r = client.post("/api/auth/login", json={"username": "demo", "password": "demo123"})
    check("employee_login", r.status_code == 200)
    if r.status_code == 200:
        et = r.json()["access_token"]
        denied = client.get("/api/dashboard", headers={"Authorization": f"Bearer {et}"})
        check("employee_blocked_admin", denied.status_code == 403)

        # 登出後 token 必須失效
        client.post("/api/auth/logout", headers={"Authorization": f"Bearer {et}"})
        me_after = client.get("/api/auth/me", headers={"Authorization": f"Bearer {et}"})
        check("logout_revokes_token", me_after.status_code == 401)

    idx = client.get("/")
    check(
        "remember_checkbox_ui",
        idx.status_code == 200 and "記住帳密" in idx.text and "remember-credentials" in idx.text,
    )
    check(
        "idle_warn_ui",
        "30秒後將自動登出" in idx.text and "繼續使用" in idx.text,
    )
    auth_js = client.get("/static/js/auth_session.js")
    check(
        "auth_session_assets",
        auth_js.status_code == 200
        and "PasswordCredential" in auth_js.text
        and "touchstart" in auth_js.text
        and "IDLE_MS" in auth_js.text,
    )
    check(
        "idle_countdown_ui",
        idx.status_code == 200
        and "idle-countdown" in idx.text
        and "自動登出" in idx.text
        and "attendance_last_activity" in auth_js.text,
    )
    check(
        "punch_no_location_gate_ui",
        "今日出勤" in idx.text
        and "env-panel" not in idx.text
        and "打卡環境" not in idx.text
        and "geolocation" not in client.get("/static/js/app.js").text.lower(),
    )
    cfg_js = client.get("/static/js/config.js")
    check(
        "frontend_api_base_config",
        cfg_js.status_code == 200 and "API_BASE" in cfg_js.text and "apiUrl" in cfg_js.text,
    )
    pub = client.get("/api/public-config")
    check(
        "public_config",
        pub.status_code == 200
        and pub.json().get("timezone") == "Asia/Taipei"
        and pub.json().get("idle_timeout_minutes") == 3,
    )
    from backend.app.config import CORS_ORIGINS

    check("cors_no_wildcard", "*" not in CORS_ORIGINS and len(CORS_ORIGINS) >= 1)

    db_path = ROOT / "data" / "attendance.sqlite3"
    check("sqlite_exists", db_path.exists(), str(db_path))

    check(
        "github_pages_workflow",
        (ROOT / ".github" / "workflows" / "deploy-pages.yml").exists()
        and (ROOT / "scripts" / "prepare_github_pages.py").exists(),
    )
    check(
        "alembic_migration",
        (ROOT / "alembic.ini").exists()
        and (ROOT / "alembic" / "versions" / "001_initial_schema.py").exists(),
    )
    check(
        "sqlite_to_pg_tool",
        (ROOT / "scripts" / "migrate_sqlite_to_postgres.py").exists(),
    )

    report = ROOT / "docs" / "ValidationChecklistReport.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Validation Checklist Report", ""]
    all_pass = True
    for name, ok, detail in CHECKS:
        all_pass = all_pass and ok
        lines.append(f"- {'PASS' if ok else 'FAIL'}: {name} {detail}")
    lines.append("")
    lines.append(f"**Result: {'ALL PASS' if all_pass else 'FAILED'}**")
    report.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nReport: {report}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
