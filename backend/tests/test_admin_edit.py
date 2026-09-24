"""管理員編輯員工與打卡管理測試。"""
from datetime import date, datetime, time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import hash_password
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import (
    AnnualStatistic,
    AttendanceDailySummary,
    AttendanceEvent,
    AuditLog,
    Employee,
    Schedule,
    Store,
)
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


@pytest.fixture(autouse=True)
def clean_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    s1 = Store(name="店舖1", code="store1", gps_radius_m=100)
    s2 = Store(name="店舖2", code="store2", gps_radius_m=100)
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
        break_start=time(12, 0),
        break_end=time(13, 0),
    )
    emp = Employee(
        name="王小明",
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
    set_setting(db, "late_break_compensation", "false")
    set_setting(db, "monthly_makeup_quota", "5")
    db.close()
    yield


def login(u="admin", p="admin123"):
    r = client.post("/api/auth/login", json={"username": u, "password": p})
    assert r.status_code == 200
    return r.json()["access_token"]


def emp_id():
    db = TestingSession()
    eid = db.query(Employee).filter(Employee.username == "emp1").first().id
    db.close()
    return eid


def add_schedule(d: date):
    db = TestingSession()
    e = db.query(Employee).filter(Employee.username == "emp1").first()
    db.add(
        Schedule(
            employee_id=e.id,
            store_id=e.store_id,
            work_date=d,
            start_time=time(8, 0),
            break_start=time(12, 0),
            break_end=time(13, 0),
            end_time=time(17, 0),
        )
    )
    db.commit()
    db.close()


def test_admin_edit_employee_name_code_store_hours():
    """1-4 編輯姓名／排班代碼／店舖／約定工時"""
    token = login()
    eid = emp_id()
    r = client.put(
        f"/api/employees/{eid}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "王小明改",
            "schedule_code": "明",
            "store_id": 2,
            "agreed_daily_hours": 7.5,
            "break_start": "12:30",
            "break_end": "13:30",
            "hire_date": "2026-01-01",
            "leave_date": None,
            "is_active": True,
            "username": "emp1",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "王小明改"
    assert data["schedule_code"] == "明"
    assert data["store_id"] == 2
    assert data["agreed_daily_hours"] == 7.5
    # employee sees updated after re-login
    et = login("emp1", "emp123")
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {et}"}).json()
    assert me["name"] == "王小明改"
    assert me["schedule_code"] == "明"
    assert me["store_id"] == 2


def _seed_punches(d: date):
    add_schedule(d)
    eid = emp_id()
    db = TestingSession()
    emp = db.query(Employee).filter(Employee.id == eid).first()
    for et, hh, mm in [
        ("START", 8, 0),
        ("BREAK_START", 12, 0),
        ("BREAK_END", 13, 0),
        ("END", 16, 18),
    ]:
        db.add(
            AttendanceEvent(
                employee_id=eid,
                store_id=emp.store_id,
                work_date=d,
                event_type=et,
                punched_at=datetime(d.year, d.month, d.day, hh, mm),
            )
        )
    db.commit()
    db.close()
    return eid


def test_admin_modify_each_event_and_recalc():
    """5-11 修改四事件並重算遲到／早退／工時"""
    d = date(2026, 9, 20)
    eid = _seed_punches(d)
    token = login()
    # END 16:18 → 17:00，早退應變 0
    r = client.put(
        "/api/admin/attendance/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": eid,
            "work_date": str(d),
            "event_type": "END",
            "punched_at": f"{d}T17:00:00",
            "reason": "修正早退",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["early_leave_minutes"] == 0

    # START 08:00 → 08:10，寬限5 → 遲到5
    r2 = client.put(
        "/api/admin/attendance/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": eid,
            "work_date": str(d),
            "event_type": "START",
            "punched_at": f"{d}T08:10:00",
        },
    )
    assert r2.status_code == 200
    assert r2.json()["late_minutes"] == 5

    for et, t in [
        ("BREAK_START", "12:05:00"),
        ("BREAK_END", "13:00:00"),
    ]:
        assert (
            client.put(
                "/api/admin/attendance/events",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "employee_id": eid,
                    "work_date": str(d),
                    "event_type": et,
                    "punched_at": f"{d}T{t}",
                },
            ).status_code
            == 200
        )

    detail = client.get(
        f"/api/admin/attendance/day-detail?employee_id={eid}&work_date={d}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert detail["late_minutes"] == 5
    assert detail["early_leave_minutes"] == 0
    # 08:10～17:00 span=530, break=55 → work=475
    assert detail["span_minutes"] == 530
    assert detail["break_minutes"] == 55
    assert detail["work_minutes"] == 475

    # employee sync
    et = login("emp1", "emp123")
    today = client.get(
        f"/api/punch/today?work_date={d}",
        headers={"Authorization": f"Bearer {et}"},
    ).json()
    assert today["events"]["START"]["at"] == "08:10"
    assert today["events"]["END"]["at"] == "17:00"

    # query sync
    q = client.get(
        f"/api/attendance/query?date_from={d}&date_to={d}&employee_id={eid}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert q[0]["actual_start"] == "08:10"
    assert q[0]["actual_end"] == "17:00"
    assert q[0]["late_minutes"] == 5


def test_admin_delete_single_and_all_sync():
    """12-15,18 單筆／全部刪除與同步"""
    d = date(2026, 9, 21)
    eid = _seed_punches(d)
    token = login()
    detail = client.get(
        f"/api/admin/attendance/day-detail?employee_id={eid}&work_date={d}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    end_id = next(e["id"] for e in detail["events"] if e["event_type"] == "END")
    r = client.delete(
        f"/api/admin/attendance/events/{end_id}?reason=誤打",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200

    et = login("emp1", "emp123")
    view = client.get(
        f"/api/punch/today?work_date={d}",
        headers={"Authorization": f"Bearer {et}"},
    ).json()
    assert view["events"]["END"]["done"] is False
    assert view["events"]["START"]["done"] is True

    r2 = client.post(
        "/api/admin/attendance/day-delete",
        headers={"Authorization": f"Bearer {token}"},
        json={"employee_id": eid, "work_date": str(d), "reason": "整天打錯"},
    )
    assert r2.status_code == 200
    assert r2.json()["deleted"] == 3

    view2 = client.get(
        f"/api/punch/today?work_date={d}",
        headers={"Authorization": f"Bearer {et}"},
    ).json()
    for t in ("START", "BREAK_START", "BREAK_END", "END"):
        assert view2["events"][t]["done"] is False

    # report sync: summary work 0
    db = TestingSession()
    s = (
        db.query(AttendanceDailySummary)
        .filter(AttendanceDailySummary.employee_id == eid, AttendanceDailySummary.work_date == d)
        .first()
    )
    assert s.work_minutes == 0
    assert s.actual_start is None
    db.close()


def test_admin_modify_report_sync_and_audit():
    """16-17,19-20 報表同步與 audit；刪除 event 不刪 audit"""
    d = date(2026, 9, 22)
    eid = _seed_punches(d)
    token = login()
    client.put(
        "/api/admin/attendance/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": eid,
            "work_date": str(d),
            "event_type": "END",
            "punched_at": f"{d}T17:00:00",
        },
    )
    annual = client.get(
        f"/api/attendance/annual?year={d.year}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert isinstance(annual, list)

    db = TestingSession()
    audits_before = db.query(AuditLog).filter(AuditLog.action == "update_punch").count()
    assert audits_before >= 1
    detail = client.get(
        f"/api/admin/attendance/day-detail?employee_id={eid}&work_date={d}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    start_id = next(e["id"] for e in detail["events"] if e["event_type"] == "START")
    client.delete(
        f"/api/admin/attendance/events/{start_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    audits_after = db.query(AuditLog).count()
    assert db.query(AuditLog).filter(AuditLog.action == "delete_punch").count() >= 1
    assert audits_after >= audits_before
    assert db.query(AttendanceEvent).filter(AttendanceEvent.id == start_id).first() is None
    assert db.query(AuditLog).filter(AuditLog.action == "delete_punch").first() is not None
    db.close()


def test_employee_cannot_access_audit_logs():
    """員工不能存取 audit_logs API"""
    d = date(2026, 9, 23)
    eid = _seed_punches(d)
    token = login()
    client.put(
        "/api/admin/attendance/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": eid,
            "work_date": str(d),
            "event_type": "END",
            "punched_at": f"{d}T17:00:00",
            "reason": "內部修正",
        },
    )
    et = login("emp1", "emp123")
    r = client.get(
        "/api/admin/attendance/audit-logs",
        headers={"Authorization": f"Bearer {et}"},
    )
    assert r.status_code == 403


def test_employee_only_sees_effective_time_no_history():
    """員工端只看到目前有效時間，不含修改歷史欄位"""
    d = date(2026, 9, 24)
    eid = _seed_punches(d)
    token = login()
    client.put(
        "/api/admin/attendance/events",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "employee_id": eid,
            "work_date": str(d),
            "event_type": "END",
            "punched_at": f"{d}T17:00:00",
            "reason": "改時間",
        },
    )
    et = login("emp1", "emp123")
    view = client.get(
        f"/api/punch/today?work_date={d}",
        headers={"Authorization": f"Bearer {et}"},
    ).json()
    assert view["events"]["END"]["at"] == "17:00"
    assert "is_makeup" not in view["events"]["END"]
    assert "original" not in str(view).lower()
    assert "audit" not in str(view).lower()
    assert "修改" not in str(view)

    own = client.get(
        f"/api/attendance/employee/{eid}",
        headers={"Authorization": f"Bearer {et}"},
    ).json()
    for row in own:
        assert "is_makeup" not in row
        assert "note" not in row
        assert "original" not in row

    # 管理員可看 audit
    logs = client.get(
        f"/api/admin/attendance/audit-logs?employee_id={eid}&work_date={d}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert any(x["action"] == "update_punch" for x in logs)
    assert any(x.get("original_time") for x in logs)
