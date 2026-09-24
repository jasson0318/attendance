"""純帳號密碼打卡：無 GPS／Wi-Fi／QR 現場驗證。"""
from datetime import date, time, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import hash_password
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import AuditLog, Employee, MakeupRecord, Schedule, Store
from backend.app.services.settings_service import set_setting

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def clean_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    s1 = Store(name="店舖1", code="store1")
    s2 = Store(name="店舖2", code="store2")
    db.add_all([s1, s2])
    db.flush()
    admin = Employee(
        name="管理員",
        schedule_code="ADMIN",
        store_id=s1.id,
        username="admin",
        password_hash=hash_password("admin123"),
        role="admin",
        is_active=True,
        agreed_daily_hours=8,
    )
    emp = Employee(
        name="測試員工",
        schedule_code="傑",
        store_id=s1.id,
        username="emp1",
        password_hash=hash_password("emp123"),
        role="employee",
        is_active=True,
        agreed_daily_hours=8,
        break_start=time(12, 0),
        break_end=time(13, 0),
    )
    db.add_all([admin, emp])
    db.commit()
    set_setting(db, "late_grace_minutes", "5")
    set_setting(db, "early_leave_grace_minutes", "5")
    set_setting(db, "late_break_compensation", "true")
    set_setting(db, "monthly_makeup_quota", "3")
    db.close()
    yield


def login(username="emp1", password="emp123"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def add_schedule(work_date: date, end_hour=17):
    db = TestingSession()
    emp = db.query(Employee).filter(Employee.username == "emp1").first()
    db.add(
        Schedule(
            employee_id=emp.id,
            store_id=emp.store_id,
            work_date=work_date,
            start_time=time(8, 0),
            break_start=time(12, 0),
            break_end=time(13, 0),
            end_time=time(end_hour, 0),
            is_day_off=False,
        )
    )
    db.commit()
    db.close()


def punch(token, event_type, **extra):
    body = {"event_type": event_type, "is_makeup": False, **extra}
    return client.post("/api/punch", headers=auth(token), json=body)


def test_login_then_start():
    token = login()
    add_schedule(date.today())
    r = punch(token, "START")
    assert r.status_code == 200, r.text


def test_start_break_end_flow():
    token = login()
    add_schedule(date.today())
    assert punch(token, "START").status_code == 200
    assert punch(token, "BREAK_START").status_code == 200
    assert punch(token, "BREAK_END").status_code == 200
    r = punch(token, "END", early_leave_reason="提早離開")
    assert r.status_code == 200, r.text


def test_unauthenticated_cannot_punch():
    r = client.post("/api/punch", json={"event_type": "START", "is_makeup": False})
    assert r.status_code == 401


def test_duplicate_start_rejected():
    token = login()
    add_schedule(date.today())
    assert punch(token, "START").status_code == 200
    r = punch(token, "START")
    assert r.status_code == 400


def test_break_start_before_start_rejected():
    token = login()
    add_schedule(date.today())
    r = punch(token, "BREAK_START")
    assert r.status_code == 400


def test_break_end_before_break_start_rejected():
    token = login()
    add_schedule(date.today())
    assert punch(token, "START").status_code == 200
    r = punch(token, "BREAK_END")
    assert r.status_code == 400


def test_end_after_break_start_without_break_end_rejected():
    token = login()
    add_schedule(date.today())
    assert punch(token, "START").status_code == 200
    assert punch(token, "BREAK_START").status_code == 200
    r = punch(token, "END", early_leave_reason="x")
    assert r.status_code == 400


def test_start_then_end_requires_no_break_reason():
    token = login()
    add_schedule(date.today())
    assert punch(token, "START").status_code == 200
    bad = punch(token, "END", early_leave_reason="提早")
    assert bad.status_code == 400
    assert "休息" in bad.json()["detail"] or "未休息" in bad.json()["detail"]
    ok = punch(
        token,
        "END",
        no_break_reason="忙碌未休息",
        early_leave_reason="提早",
    )
    assert ok.status_code == 200, ok.text


def test_early_end_requires_reason():
    token = login()
    add_schedule(date.today(), end_hour=23)
    assert punch(token, "START").status_code == 200
    assert punch(token, "BREAK_START").status_code == 200
    assert punch(token, "BREAK_END").status_code == 200
    bad = punch(token, "END")
    assert bad.status_code == 400
    ok = punch(token, "END", early_leave_reason="臨時有事")
    assert ok.status_code == 200, ok.text


def test_unscheduled_start_requires_reason_then_ok():
    token = login()
    bad = punch(token, "START")
    assert bad.status_code == 400
    ok = punch(token, "START", unscheduled_reason="支援其他門市")
    assert ok.status_code == 200, ok.text
    assert ok.json().get("attendance_status") == "UNSCHEDULED_ATTENDANCE"


def test_makeup_and_over_quota():
    token = login()
    d = date.today() - timedelta(days=2)
    for i, et in enumerate(["START", "BREAK_START", "BREAK_END"]):
        hour = 8 + i
        r = client.post(
            "/api/punch",
            headers=auth(token),
            json={
                "event_type": et,
                "is_makeup": True,
                "work_date": str(d),
                "makeup_reason": f"補{i}",
                "punched_at": f"{d}T{hour:02d}:00:00",
            },
        )
        assert r.status_code == 200, r.text
    r4 = client.post(
        "/api/punch",
        headers=auth(token),
        json={
            "event_type": "END",
            "is_makeup": True,
            "work_date": str(d),
            "makeup_reason": "超額補",
            "punched_at": f"{d}T17:00:00",
        },
    )
    assert r4.status_code == 200, r4.text
    assert r4.json().get("over_quota") is True
    db = TestingSession()
    assert db.query(MakeupRecord).filter(MakeupRecord.over_quota == True).count() >= 1  # noqa: E712
    assert db.query(AuditLog).filter(AuditLog.action == "makeup_punch").count() >= 4
    db.close()


def test_employee_cannot_read_audit_logs():
    token = login()
    r = client.get("/api/admin/attendance/audit-logs", headers=auth(token))
    assert r.status_code == 403


def test_admin_edit_writes_audit():
    admin = login("admin", "admin123")
    emp_token = login()
    add_schedule(date.today())
    assert punch(emp_token, "START").status_code == 200

    db = TestingSession()
    emp = db.query(Employee).filter(Employee.username == "emp1").first()
    emp_id = emp.id
    db.close()

    upd = client.put(
        "/api/admin/attendance/events",
        headers=auth(admin),
        json={
            "employee_id": emp_id,
            "work_date": str(date.today()),
            "event_type": "START",
            "punched_at": f"{date.today()}T08:05:00",
            "reason": "管理員修正",
        },
    )
    assert upd.status_code == 200, upd.text
    event_id = upd.json().get("event_id")
    logs = client.get(
        f"/api/admin/attendance/audit-logs?employee_id={emp_id}",
        headers=auth(admin),
    )
    assert logs.status_code == 200
    assert len(logs.json()) >= 1

    assert event_id
    delete = client.delete(
        f"/api/admin/attendance/events/{event_id}?reason=管理員刪除",
        headers=auth(admin),
    )
    assert delete.status_code == 200, delete.text
    logs2 = client.get(
        f"/api/admin/attendance/audit-logs?employee_id={emp_id}",
        headers=auth(admin),
    )
    assert logs2.status_code == 200
    assert len(logs2.json()) >= 2


def test_logout_revokes_token():
    token = login()
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 200
    client.post("/api/auth/logout", headers=auth(token))
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 401


def test_no_environment_endpoint():
    token = login()
    r = client.post("/api/punch/environment", headers=auth(token), json={})
    assert r.status_code == 404


def test_punch_without_gps_fields_ok():
    token = login()
    add_schedule(date.today())
    r = punch(token, "START")
    assert r.status_code == 200, r.text
    assert punch(token, "BREAK_START").status_code == 200


def test_settings_have_no_gps_wifi():
    admin = login("admin", "admin123")
    r = client.get("/api/settings", headers=auth(admin))
    assert r.status_code == 200
    data = r.json()
    assert "require_gps" not in data
    assert "require_wifi" not in data
    assert "wifi_verification_mode" not in data


def test_frontend_has_no_location_gate():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    app_js = (ROOT / "frontend" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    admin_js = (ROOT / "frontend" / "static" / "js" / "admin.js").read_text(encoding="utf-8")
    assert "今日出勤" in index
    assert "打卡環境" not in index
    assert "env-panel" not in index
    assert "geolocation" not in app_js.lower()
    assert "getCurrentPosition" not in app_js
    assert "/api/punch/environment" not in app_js
    assert "gps_lat" not in admin_js
    assert "require_gps" not in admin_js
    assert "wifi_ssid" not in admin_js


def test_secret_key_not_hardcoded_default():
    from backend.app import config

    assert config.SECRET_KEY != "attendance-system-change-me-in-production-2026"
    assert len(config.SECRET_KEY) >= 32


def test_idle_countdown_assets_still_present():
    index = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
    auth_js = (ROOT / "frontend" / "static" / "js" / "auth_session.js").read_text(
        encoding="utf-8"
    )
    assert "idle-countdown" in index
    assert "自動登出" in index
    assert "IDLE_MS" in auth_js
    assert "touchstart" in auth_js
