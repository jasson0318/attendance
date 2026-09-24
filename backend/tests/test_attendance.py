"""自動化測試：出勤計算、權限、補打卡、生物辨識移除。"""
from datetime import date, datetime, time
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
from backend.app.services.calc import (
    CalcSettings,
    PunchTimes,
    ScheduleTimes,
    apply_late_break_compensation,
    calc_late_minutes,
    calc_span_minutes,
    calc_work_minutes,
    compute_daily,
    count_missing_events,
    is_absent,
    makeup_warning_message,
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
    emp2 = Employee(
        name="其他員工",
        schedule_code="小明",
        store_id=s2.id,
        username="emp2",
        password_hash=hash_password("emp123"),
        role="employee",
        is_active=True,
        agreed_daily_hours=8,
    )
    db.add_all([admin, emp, emp2])
    db.commit()
    set_setting(db, "late_grace_minutes", "5")
    set_setting(db, "early_leave_grace_minutes", "5")
    set_setting(db, "late_break_compensation", "true")
    set_setting(db, "monthly_makeup_quota", "5")
    db.close()
    yield


def login(username, password):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200
    return r.json()["access_token"]


def _full_schedule(d: date) -> ScheduleTimes:
    return ScheduleTimes(
        work_date=d,
        start=time(8, 0),
        break_start=time(12, 0),
        break_end=time(13, 0),
        end=time(17, 0),
        has_schedule=True,
    )


def test_01_grace_no_late():
    assert calc_late_minutes(time(8, 0), datetime(2026, 9, 1, 8, 5), 5) == 0


def test_02_late_one_minute():
    assert calc_late_minutes(time(8, 0), datetime(2026, 9, 1, 8, 6), 5) == 1
    assert calc_late_minutes(time(8, 0), datetime(2026, 9, 1, 8, 10), 5) == 5


def test_03_grace_does_not_change_break():
    sched = _full_schedule(date(2026, 9, 1))
    punch = PunchTimes(
        start=datetime(2026, 9, 1, 8, 5),
        break_start=datetime(2026, 9, 1, 12, 0),
        break_end=datetime(2026, 9, 1, 13, 0),
        end=datetime(2026, 9, 1, 17, 0),
    )
    result = compute_daily(sched, punch, CalcSettings(late_grace_minutes=5, late_break_compensation=False))
    assert result.scheduled_break_start == time(12, 0)
    assert result.scheduled_break_end == time(13, 0)


def test_04_grace_does_not_change_end():
    sched = _full_schedule(date(2026, 9, 1))
    punch = PunchTimes(
        start=datetime(2026, 9, 1, 8, 5),
        break_start=datetime(2026, 9, 1, 12, 0),
        break_end=datetime(2026, 9, 1, 13, 0),
        end=datetime(2026, 9, 1, 17, 0),
    )
    result = compute_daily(sched, punch, CalcSettings(late_grace_minutes=5))
    assert result.scheduled_end == time(17, 0)
    assert result.late_minutes == 0


def test_05_late_break_compensation_on():
    effective, compensated = apply_late_break_compensation(5, 60, 55, True)
    assert compensated == 5
    assert effective == 0


def test_06_late_break_compensation_off():
    effective, compensated = apply_late_break_compensation(5, 60, 55, False)
    assert compensated == 0
    assert effective == 5


def test_07_one_missing_is_one_makeup():
    sched = _full_schedule(date(2026, 9, 1))
    punch = PunchTimes(
        break_start=datetime(2026, 9, 1, 12, 0),
        break_end=datetime(2026, 9, 1, 13, 0),
        end=datetime(2026, 9, 1, 17, 0),
    )
    assert count_missing_events(punch, sched) == ["START"]


def test_08_four_missing_is_four():
    assert len(count_missing_events(PunchTimes(), _full_schedule(date(2026, 9, 1)))) == 4


def test_09_10_over_quota_still_allowed_and_recorded():
    token = login("emp1", "emp123")
    warnings = []
    for day in range(1, 7):
        r = client.post(
            "/api/punch",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "event_type": "START",
                "is_makeup": True,
                "work_date": f"2026-09-{day:02d}",
                "punched_at": f"2026-09-{day:02d}T08:00:00",
                "reason": f"忘記打卡 day{day}",
            },
        )
        assert r.status_code == 200, r.text
        if r.json().get("warning"):
            warnings.append(r.json()["warning"])
    assert len(warnings) >= 1
    assert "第6次" in warnings[-1]
    assert "超過公司設定的5次" in warnings[-1]

    month = date.today().strftime("%Y-%m")
    records = client.get(
        f"/api/attendance/makeup?month={month}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    assert any(x["over_quota"] and x["performance_flag"] for x in records)


def test_11_no_schedule_not_absent():
    assert is_absent(ScheduleTimes(work_date=date(2026, 9, 1), has_schedule=False), PunchTimes()) is False


def test_12_day_off_not_absent():
    assert (
        is_absent(
            ScheduleTimes(work_date=date(2026, 9, 1), has_schedule=True, is_day_off=True),
            PunchTimes(),
        )
        is False
    )


def test_13_work_minus_break():
    start = datetime(2026, 9, 1, 8, 3)
    bs = datetime(2026, 9, 1, 12, 5)
    be = datetime(2026, 9, 1, 13, 0)
    end = datetime(2026, 9, 1, 17, 2)
    assert calc_work_minutes(start, end, bs, be) == 8 * 60 + 4


def test_14_span_and_work_separate():
    start = datetime(2026, 9, 1, 8, 3)
    bs = datetime(2026, 9, 1, 12, 5)
    be = datetime(2026, 9, 1, 13, 0)
    end = datetime(2026, 9, 1, 17, 2)
    assert calc_span_minutes(start, end) == 8 * 60 + 59
    assert calc_work_minutes(start, end, bs, be) == 8 * 60 + 4


def test_15_employee_cannot_view_others():
    token = login("emp1", "emp123")
    db = TestingSession()
    oid = db.query(Employee).filter(Employee.username == "emp2").first().id
    db.close()
    r = client.get(f"/api/attendance/employee/{oid}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_16_employee_cannot_use_admin_api():
    token = login("emp1", "emp123")
    assert client.get("/api/employees", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.get("/api/settings", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    assert client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_makeup_no_schedule_allowed():
    """1. 無排班仍可補打卡"""
    token = login("emp1", "emp123")
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "START",
            "is_makeup": True,
            "work_date": "2026-08-10",
            "punched_at": "2026-08-10T08:00:00",
            "reason": "忘記打卡",
        },
    )
    assert r.status_code == 200, r.text


def test_makeup_past_date_allowed():
    """2. 過去日期仍可補打卡"""
    token = login("emp1", "emp123")
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "END",
            "is_makeup": True,
            "work_date": "2026-07-01",
            "punched_at": "2026-07-01T17:00:00",
            "reason": "手機故障",
        },
    )
    assert r.status_code == 200, r.text


def test_makeup_reason_required_empty():
    """3. 補打卡原因為空時不可送出"""
    token = login("emp1", "emp123")
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "START",
            "is_makeup": True,
            "work_date": "2026-06-01",
            "reason": "   ",
        },
    )
    assert r.status_code == 400
    assert "請填寫補打卡原因" in r.json()["detail"]


def test_makeup_reason_ok_and_saved():
    """4+5. 有填原因可以送出，且原因會保存"""
    token = login("emp1", "emp123")
    reason = "今天上班時忘記打卡"
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "BREAK_START",
            "is_makeup": True,
            "work_date": "2026-06-02",
            "punched_at": "2026-06-02T12:00:00",
            "reason": reason,
        },
    )
    assert r.status_code == 200, r.text
    month = date.today().strftime("%Y-%m")
    records = client.get(
        f"/api/attendance/makeup?month={month}",
        headers={"Authorization": f"Bearer {token}"},
    ).json()
    matched = [x for x in records if x["work_date"] == "2026-06-02" and x["event_type"] == "BREAK_START"]
    assert matched
    assert matched[0]["reason"] == reason
    db = TestingSession()
    row = (
        db.query(MakeupRecord)
        .filter(MakeupRecord.work_date == date(2026, 6, 2), MakeupRecord.event_type == "BREAK_START")
        .first()
    )
    assert row is not None
    assert row.reason == reason
    assert row.store_id is not None
    assert row.submitted_at is not None
    assert row.punched_at is not None
    assert row.missing_event == "BREAK_START"
    audit = db.query(AuditLog).filter(AuditLog.action == "makeup_punch").count()
    assert audit >= 1
    db.close()


def test_makeup_duplicate_forbidden():
    """6. 同一日期同一事件不能重複補打卡"""
    token = login("emp1", "emp123")
    body = {
        "event_type": "START",
        "is_makeup": True,
        "work_date": "2026-05-15",
        "punched_at": "2026-05-15T08:00:00",
        "reason": "第一次補",
    }
    assert client.post("/api/punch", headers={"Authorization": f"Bearer {token}"}, json=body).status_code == 200
    r2 = client.post("/api/punch", headers={"Authorization": f"Bearer {token}"}, json={**body, "reason": "第二次"})
    assert r2.status_code == 400
    assert "已有打卡紀錄" in r2.json()["detail"]


def test_makeup_over_quota_still_ok_and_flagged():
    """7+8. 超過額度仍可補，並留考績紀錄"""
    token = login("emp1", "emp123")
    for i in range(1, 7):
        r = client.post(
            "/api/punch",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "event_type": "START",
                "is_makeup": True,
                "work_date": f"2026-04-{i:02d}",
                "punched_at": f"2026-04-{i:02d}T08:00:00",
                "reason": f"補第{i}次",
            },
        )
        assert r.status_code == 200, r.text
    assert r.json().get("over_quota") is True
    assert r.json().get("warning")
    db = TestingSession()
    flagged = db.query(MakeupRecord).filter(MakeupRecord.over_quota == True).count()  # noqa: E712
    assert flagged >= 1
    db.close()


def test_webauthn_api_removed():
    """9. 生物辨識相關 API 已移除"""
    token = login("emp1", "emp123")
    for path in (
        "/api/webauthn/register/options",
        "/api/webauthn/register/verify",
        "/api/webauthn/authenticate/options",
        "/api/webauthn/authenticate/verify",
    ):
        r = client.post(path, headers={"Authorization": f"Bearer {token}"}, json={})
        assert r.status_code == 404


def test_webauthn_ui_removed():
    """10. 生物辨識按鈕已移除"""
    index = Path(__file__).resolve().parents[2] / "frontend" / "index.html"
    js = Path(__file__).resolve().parents[2] / "frontend" / "static" / "js" / "app.js"
    text = index.read_text(encoding="utf-8") + js.read_text(encoding="utf-8")
    assert "註冊生物辨識" not in text
    assert "bio-reg" not in text
    assert "webauthn" not in text.lower()
    assert "maybeBiometrics" not in text
    settings_js = (Path(__file__).resolve().parents[2] / "frontend" / "static" / "js" / "admin.js").read_text(
        encoding="utf-8"
    )
    assert "生物辨識" not in settings_js
    assert "require_biometrics" not in settings_js


def test_scheduled_normal_punch():
    """1. 有排班可以正常打卡"""
    db = TestingSession()
    emp = db.query(Employee).filter(Employee.username == "emp1").first()
    today = date.today()
    db.add(
        Schedule(
            employee_id=emp.id,
            store_id=emp.store_id,
            work_date=today,
            start_time=time(8, 0),
            break_start=time(12, 0),
            break_end=time(13, 0),
            end_time=time(17, 0),
        )
    )
    db.commit()
    db.close()
    token = login("emp1", "emp123")
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "START", "is_makeup": False},
    )
    assert r.status_code == 200, r.text


def test_unscheduled_start_without_reason_rejected():
    """2+3. 無排班可打卡，但沒填原因不可送出"""
    token = login("emp1", "emp123")
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={"event_type": "START", "is_makeup": False},
    )
    assert r.status_code == 400
    assert "請先填寫出勤原因" in r.json()["detail"]


def test_unscheduled_start_with_reason_ok_and_saved():
    """4+5. 無排班且有填原因 → 成功，原因會保存"""
    from backend.app.models import UnscheduledAttendance

    token = login("emp1", "emp123")
    reason = "支援其他門市"
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "START",
            "is_makeup": False,
            "unscheduled_reason": reason,
            "punch_store_id": 2,
        },
    )
    assert r.status_code == 200, r.text
    db = TestingSession()
    row = db.query(UnscheduledAttendance).filter(UnscheduledAttendance.employee_id == 2).first()
    # emp1 id may vary - query by reason
    row = (
        db.query(UnscheduledAttendance)
        .filter(UnscheduledAttendance.unscheduled_reason == reason)
        .first()
    )
    assert row is not None
    assert row.home_store_id != row.punch_store_id or row.punch_store_id == 2
    assert row.unscheduled_reason == reason
    db.close()


def test_unscheduled_full_day_not_absent():
    """6+7. 無排班上班後可休息下班，且不算曠職"""
    from backend.app.models import AttendanceDailySummary, UnscheduledAttendance

    token = login("emp1", "emp123")
    d = "2026-03-10"
    assert (
        client.post(
            "/api/punch",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "event_type": "START",
                "is_makeup": False,
                "work_date": d,
                "unscheduled_reason": "臨時支援",
            },
        ).status_code
        == 200
    )
    for et in ("BREAK_START", "BREAK_END", "END"):
        r = client.post(
            "/api/punch",
            headers={"Authorization": f"Bearer {token}"},
            json={"event_type": et, "is_makeup": False, "work_date": d},
        )
        assert r.status_code == 200, r.text

    db = TestingSession()
    emp = db.query(Employee).filter(Employee.username == "emp1").first()
    summary = (
        db.query(AttendanceDailySummary)
        .filter(
            AttendanceDailySummary.employee_id == emp.id,
            AttendanceDailySummary.work_date == date(2026, 3, 10),
        )
        .first()
    )
    assert summary is not None
    assert summary.is_absent is False
    assert summary.attendance_status == "UNSCHEDULED_ATTENDANCE"
    assert summary.unscheduled_reason == "臨時支援"
    # calc unit also
    result = compute_daily(
        ScheduleTimes(work_date=date(2026, 3, 10), has_schedule=False),
        PunchTimes(
            start=datetime(2026, 3, 10, 8, 3),
            break_start=datetime(2026, 3, 10, 12, 0),
            break_end=datetime(2026, 3, 10, 13, 0),
            end=datetime(2026, 3, 10, 17, 0),
        ),
        CalcSettings(),
    )
    assert result.is_absent is False
    assert result.attendance_status == "UNSCHEDULED_ATTENDANCE"
    db.close()


def test_unscheduled_no_location_required():
    """無排班出勤：僅需原因，不需 GPS／現場驗證。"""
    token = login("emp1", "emp123")
    ok = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "START",
            "is_makeup": False,
            "work_date": "2026-03-11",
            "unscheduled_reason": "支援",
            "punch_store_id": 1,
        },
    )
    assert ok.status_code == 200, ok.text


def test_unscheduled_and_makeup_reasons_separate():
    """9. 無排班出勤與補打卡原因分開保存"""
    from backend.app.models import UnscheduledAttendance

    token = login("emp1", "emp123")
    client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "START",
            "is_makeup": False,
            "work_date": "2026-03-12",
            "unscheduled_reason": "支援其他門市",
        },
    )
    client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "END",
            "is_makeup": True,
            "work_date": "2026-03-13",
            "punched_at": "2026-03-13T17:00:00",
            "makeup_reason": "早上忘記打卡",
            "reason": "早上忘記打卡",
        },
    )
    db = TestingSession()
    u = (
        db.query(UnscheduledAttendance)
        .filter(UnscheduledAttendance.work_date == date(2026, 3, 12))
        .first()
    )
    m = (
        db.query(MakeupRecord)
        .filter(MakeupRecord.work_date == date(2026, 3, 13))
        .first()
    )
    assert u.unscheduled_reason == "支援其他門市"
    assert m.reason == "早上忘記打卡"
    assert u.unscheduled_reason != m.reason
    db.close()


def test_makeup_still_no_schedule_restriction():
    """10. 補打卡仍然不受排班限制"""
    token = login("emp1", "emp123")
    r = client.post(
        "/api/punch",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "event_type": "START",
            "is_makeup": True,
            "work_date": "2026-02-01",
            "punched_at": "2026-02-01T08:00:00",
            "reason": "忘記打卡",
        },
    )
    assert r.status_code == 200, r.text
