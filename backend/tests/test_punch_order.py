"""嚴格打卡順序、二次確認、未休息／提前下班例外。"""
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import hash_password
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import (
    AttendanceDailySummary,
    AttendanceEvent,
    AuditLog,
    Employee,
    Schedule,
    Store,
)
from backend.app.services.punch_order import (
    allowed_buttons,
    is_before_scheduled_end,
    validate_normal_punch,
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

ROOT = Path(__file__).resolve().parents[2]
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "frontend" / "static" / "js" / "app.js").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def clean_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    s1 = Store(name="店舖1", code="store1", gps_radius_m=100)
    db.add(s1)
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
    set_setting(db, "early_leave_grace_minutes", "5")
    db.close()
    yield


def login(user="emp1", pw="emp123"):
    r = client.post("/api/auth/login", json={"username": user, "password": pw})
    assert r.status_code == 200
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def emp_id():
    db = TestingSession()
    e = db.query(Employee).filter(Employee.username == "emp1").first()
    eid = e.id
    sid = e.store_id
    db.close()
    return eid, sid


def add_today_schedule(*, end_time=time(0, 0), work_date=None):
    """預設 end=00:00，讓「現在」通常已過下班時間，避免誤觸提前下班。"""
    eid, sid = emp_id()
    d = work_date or date.today()
    db = TestingSession()
    db.add(
        Schedule(
            employee_id=eid,
            store_id=sid,
            work_date=d,
            start_time=time(8, 0),
            break_start=time(12, 0),
            break_end=time(13, 0),
            end_time=end_time,
        )
    )
    db.commit()
    db.close()
    return d


def punch(token, event_type, **extra):
    body = {"event_type": event_type, "is_makeup": False, **extra}
    return client.post("/api/punch", headers=auth(token), json=body)


# --- 二次確認（前端） ---

def test_confirm_required_for_all_four_events():
    for label in ("上班打卡", "開始休息", "結束休息", "下班打卡"):
        assert f"確認要進行「{label}」嗎？" in APP_JS
    assert "確認打卡" in INDEX
    assert "confirm-time" in INDEX
    assert "openConfirm" in APP_JS
    assert "closeConfirm" in APP_JS
    # 取消不得送出：確認後才 doPunch
    assert "confirm-ok" in APP_JS
    assert APP_JS.index("openConfirm") < APP_JS.index("async function doPunch")


# --- 順序拒絕 ---

def test_break_start_without_start_rejected():
    add_today_schedule()
    token = login()
    r = punch(token, "BREAK_START")
    assert r.status_code == 400
    assert "請先完成上班打卡" in r.json()["detail"]


def test_end_without_start_rejected():
    add_today_schedule()
    token = login()
    r = punch(token, "END")
    assert r.status_code == 400
    assert "請先完成上班打卡" in r.json()["detail"]


def test_break_end_without_break_start_rejected():
    add_today_schedule()
    token = login()
    assert punch(token, "START").status_code == 200
    r = punch(token, "BREAK_END")
    assert r.status_code == 400
    assert "請先完成開始休息打卡" in r.json()["detail"]


def test_end_without_break_end_after_break_start_rejected():
    add_today_schedule()
    token = login()
    assert punch(token, "START").status_code == 200
    assert punch(token, "BREAK_START").status_code == 200
    r = punch(token, "END")
    assert r.status_code == 400
    assert "請先完成結束休息打卡" in r.json()["detail"]


def test_normal_four_steps_ok():
    add_today_schedule(end_time=time(0, 0))
    token = login()
    for et in ("START", "BREAK_START", "BREAK_END", "END"):
        r = punch(token, et)
        assert r.status_code == 200, r.text
    db = TestingSession()
    eid, _ = emp_id()
    types = {
        e.event_type
        for e in db.query(AttendanceEvent).filter(AttendanceEvent.employee_id == eid).all()
    }
    assert types == {"START", "BREAK_START", "BREAK_END", "END"}
    db.close()


def test_duplicate_events_rejected():
    add_today_schedule()
    token = login()
    assert punch(token, "START").status_code == 200
    r = punch(token, "START")
    assert r.status_code == 400
    assert "上班打卡已完成" in r.json()["detail"]

    assert punch(token, "BREAK_START").status_code == 200
    r = punch(token, "BREAK_START")
    assert r.status_code == 400
    assert "開始休息已完成" in r.json()["detail"]

    assert punch(token, "BREAK_END").status_code == 200
    r = punch(token, "BREAK_END")
    assert r.status_code == 400
    assert "結束休息已完成" in r.json()["detail"]

    assert punch(token, "END").status_code == 200
    r = punch(token, "END")
    assert r.status_code == 400
    assert "下班打卡已完成" in r.json()["detail"]


def test_backend_rejects_wrong_order_directly():
    """後端直接呼叫錯誤順序 API 也會拒絕。"""
    add_today_schedule()
    token = login()
    assert punch(token, "END").status_code == 400
    assert punch(token, "BREAK_START").status_code == 400


# --- 未休息例外 ---

def test_start_then_end_without_break_requires_reason():
    add_today_schedule(end_time=time(0, 0))
    token = login()
    assert punch(token, "START").status_code == 200
    r = punch(token, "END")
    assert r.status_code == 400
    assert "未休息原因" in r.json()["detail"]


def test_start_then_end_with_no_break_reason_ok():
    add_today_schedule(end_time=time(0, 0))
    token = login()
    assert punch(token, "START").status_code == 200
    r = punch(token, "END", no_break_reason="今日工作繁忙，未休息")
    assert r.status_code == 200, r.text
    eid, _ = emp_id()
    db = TestingSession()
    types = {
        e.event_type
        for e in db.query(AttendanceEvent).filter(AttendanceEvent.employee_id == eid).all()
    }
    assert types == {"START", "END"}
    assert "BREAK_START" not in types
    assert "BREAK_END" not in types
    summary = (
        db.query(AttendanceDailySummary)
        .filter(AttendanceDailySummary.employee_id == eid)
        .first()
    )
    assert summary.no_break_reason == "今日工作繁忙，未休息"
    assert not summary.early_leave_reason
    db.close()


def test_break_start_must_finish_before_end():
    add_today_schedule()
    token = login()
    assert punch(token, "START").status_code == 200
    assert punch(token, "BREAK_START").status_code == 200
    r = punch(token, "END", no_break_reason="x", early_leave_reason="y")
    assert r.status_code == 400
    assert "結束休息" in r.json()["detail"]
    assert punch(token, "BREAK_END").status_code == 200
    assert punch(token, "END").status_code == 200


# --- 提前下班 ---

def test_early_leave_requires_reason():
    add_today_schedule(end_time=time(23, 59))
    token = login()
    for et in ("START", "BREAK_START", "BREAK_END"):
        assert punch(token, et).status_code == 200
    r = punch(token, "END")
    assert r.status_code == 400
    assert "提前下班原因" in r.json()["detail"]


def test_early_leave_with_reason_ok():
    add_today_schedule(end_time=time(23, 59))
    token = login()
    for et in ("START", "BREAK_START", "BREAK_END"):
        assert punch(token, et).status_code == 200
    r = punch(token, "END", early_leave_reason="臨時有事")
    assert r.status_code == 200, r.text
    eid, _ = emp_id()
    db = TestingSession()
    summary = (
        db.query(AttendanceDailySummary)
        .filter(AttendanceDailySummary.employee_id == eid)
        .first()
    )
    assert summary.early_leave_reason == "臨時有事"
    assert not summary.no_break_reason
    db.close()


def test_on_time_end_no_early_reason_needed():
    add_today_schedule(end_time=time(0, 0))
    token = login()
    for et in ("START", "BREAK_START", "BREAK_END", "END"):
        assert punch(token, et).status_code == 200


def test_grace_does_not_waive_early_leave_reason():
    """早退寬限 ≠ 免除提前下班原因。"""
    set_setting(TestingSession(), "early_leave_grace_minutes", "60")
    # 排班 23:59，現在一定早於；即使寬限很大仍要原因
    assert is_before_scheduled_end(datetime.now(), time(23, 59), date.today())
    r = validate_normal_punch(
        "END",
        {"START", "BREAK_START", "BREAK_END"},
        now=datetime.now(),
        work_date=date.today(),
        scheduled_end=time(23, 59),
        early_leave_reason="",
    )
    assert not r.ok
    assert "提前下班原因" in r.error


def test_no_break_and_early_need_both_reasons():
    add_today_schedule(end_time=time(23, 59))
    token = login()
    assert punch(token, "START").status_code == 200
    r = punch(token, "END", no_break_reason="工作繁忙")
    assert r.status_code == 400
    assert "提前下班" in r.json()["detail"]
    r = punch(
        token,
        "END",
        no_break_reason="工作繁忙",
        early_leave_reason="臨時有事",
    )
    assert r.status_code == 200, r.text
    eid, _ = emp_id()
    db = TestingSession()
    summary = (
        db.query(AttendanceDailySummary)
        .filter(AttendanceDailySummary.employee_id == eid)
        .first()
    )
    assert summary.no_break_reason == "工作繁忙"
    assert summary.early_leave_reason == "臨時有事"
    types = {
        e.event_type
        for e in db.query(AttendanceEvent).filter(AttendanceEvent.employee_id == eid).all()
    }
    assert types == {"START", "END"}
    db.close()


def test_reasons_stored_separately():
    add_today_schedule(end_time=time(23, 59))
    token = login()
    punch(token, "START")
    punch(token, "END", no_break_reason="NB", early_leave_reason="EL")
    eid, _ = emp_id()
    db = TestingSession()
    s = db.query(AttendanceDailySummary).filter(AttendanceDailySummary.employee_id == eid).first()
    assert s.no_break_reason == "NB"
    assert s.early_leave_reason == "EL"
    db.close()


def test_admin_query_shows_both_reasons():
    add_today_schedule(end_time=time(23, 59))
    token = login()
    punch(token, "START")
    punch(token, "END", no_break_reason="工作繁忙", early_leave_reason="臨時有事")
    admin = login("admin", "admin123")
    rows = client.get("/api/attendance/query", headers=auth(admin)).json()
    assert any(
        r.get("no_break_reason") == "工作繁忙" and r.get("early_leave_reason") == "臨時有事"
        for r in rows
    )


def test_employee_sees_effective_state_not_audit():
    add_today_schedule(end_time=time(0, 0))
    token = login()
    punch(token, "START")
    punch(token, "END", no_break_reason="忙")
    today = client.get("/api/punch/today", headers=auth(token)).json()
    assert today["events"]["START"]["done"] is True
    assert today["events"]["END"]["done"] is True
    assert today["events"]["BREAK_START"].get("skipped") or today["no_break_reason"]
    assert today["no_break_reason"] == "忙"
    # 員工端 today 不含 audit
    assert "audit" not in today
    emp_token = token
    admin = login("admin", "admin123")
    audit = client.get("/api/admin/attendance/audit-logs", headers=auth(admin))
    assert audit.status_code == 200
    denied = client.get("/api/admin/attendance/audit-logs", headers=auth(emp_token))
    assert denied.status_code in (401, 403)


def test_unscheduled_still_works_with_order():
    token = login()
    r = punch(token, "START")
    assert r.status_code == 400
    assert punch(token, "START", unscheduled_reason="支援").status_code == 200
    for et in ("BREAK_START", "BREAK_END", "END"):
        assert punch(token, et).status_code == 200


def test_makeup_bypasses_order():
    add_today_schedule()
    token = login()
    d = str(date.today())
    # 直接補 END（無 START）應允許
    r = client.post(
        "/api/punch",
        headers=auth(token),
        json={
            "event_type": "END",
            "is_makeup": True,
            "work_date": d,
            "makeup_reason": "忘記下班打卡",
            "punched_at": f"{d}T17:00:00",
        },
    )
    assert r.status_code == 200, r.text


def test_admin_edit_bypasses_order():
    add_today_schedule()
    eid, sid = emp_id()
    d = date.today()
    db = TestingSession()
    db.add(
        AttendanceEvent(
            employee_id=eid,
            store_id=sid,
            work_date=d,
            event_type="END",
            punched_at=datetime.combine(d, time(17, 0)),
            is_makeup=False,
        )
    )
    db.commit()
    db.close()
    admin = login("admin", "admin123")
    r = client.put(
        "/api/admin/attendance/events",
        headers=auth(admin),
        json={
            "employee_id": eid,
            "work_date": str(d),
            "event_type": "START",
            "punched_at": f"{d}T08:00:00",
            "reason": "管理員補建上班",
        },
    )
    assert r.status_code == 200, r.text
    # 可刪除 BREAK 相關（即使沒有）— 刪除 END 再驗證 audit
    events = (
        client.get(
            f"/api/admin/attendance/day-detail?employee_id={eid}&work_date={d}",
            headers=auth(admin),
        )
    )
    if events.status_code != 200:
        events = client.get(
            f"/api/admin/attendance/day?employee_id={eid}&work_date={d}",
            headers=auth(admin),
        )
    # 刪除 END 不受順序限制
    db = TestingSession()
    end_ev = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == eid,
            AttendanceEvent.event_type == "END",
        )
        .first()
    )
    end_id = end_ev.id
    db.close()
    deleted = client.delete(
        f"/api/admin/attendance/events/{end_id}?reason=修正錯誤",
        headers=auth(admin),
    )
    assert deleted.status_code == 200, deleted.text
    logs = client.get("/api/admin/attendance/audit-logs", headers=auth(admin))
    assert logs.status_code == 200
    assert len(logs.json()) >= 1


def test_allowed_buttons_logic():
    assert allowed_buttons(set())["START"] is True
    assert allowed_buttons(set())["BREAK_START"] is False
    assert allowed_buttons({"START"})["BREAK_START"] is True
    assert allowed_buttons({"START"})["END"] is True
    assert allowed_buttons({"START", "BREAK_START"})["END"] is False
    assert allowed_buttons({"START", "BREAK_START", "BREAK_END"})["END"] is True
