from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import (
    AnnualStatistic,
    AttendanceDailySummary,
    AttendanceEvent,
    Employee,
    MakeupRecord,
    Store,
)
from ..services.summary_service import rebuild_annual, rebuild_daily_summary
from ..timeutil import today_local

router = APIRouter(prefix="/api/attendance", tags=["attendance"])


@router.get("/query")
def query_attendance(
    date_from: date | None = None,
    date_to: date | None = None,
    month: str | None = None,
    employee_id: int | None = None,
    store_id: int | None = None,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    q = db.query(AttendanceDailySummary)
    if user.role != "admin":
        q = q.filter(AttendanceDailySummary.employee_id == user.id)
    else:
        if employee_id:
            q = q.filter(AttendanceDailySummary.employee_id == employee_id)
        if store_id:
            q = q.filter(AttendanceDailySummary.store_id == store_id)
    if month:
        y, m = map(int, month.split("-"))
        from calendar import monthrange

        last = monthrange(y, m)[1]
        q = q.filter(
            AttendanceDailySummary.work_date >= date(y, m, 1),
            AttendanceDailySummary.work_date <= date(y, m, last),
        )
    if date_from:
        q = q.filter(AttendanceDailySummary.work_date >= date_from)
    if date_to:
        q = q.filter(AttendanceDailySummary.work_date <= date_to)

    rows = q.order_by(AttendanceDailySummary.work_date.desc()).limit(500).all()
    result = []
    for s in rows:
        emp = db.query(Employee).filter(Employee.id == s.employee_id).first()
        store = db.query(Store).filter(Store.id == s.store_id).first()
        result.append(
            {
                "employee_id": s.employee_id,
                "employee_name": emp.name if emp else "",
                "store_id": s.store_id,
                "store_name": store.name if store else "",
                "home_store_id": s.home_store_id,
                "punch_store_id": s.punch_store_id,
                "work_date": str(s.work_date),
                "has_schedule": s.has_schedule,
                "is_day_off": s.is_day_off,
                "attendance_status": s.attendance_status,
                "attendance_status_label": {
                    "NORMAL": "正常出勤",
                    "UNSCHEDULED_ATTENDANCE": "無排班出勤",
                    "ABSENT": "曠職",
                    "DAY_OFF": "休假",
                    "NO_SCHEDULE": "無排班",
                }.get(s.attendance_status or "", s.attendance_status or ""),
                "unscheduled_reason": s.unscheduled_reason or "",
                "no_break_reason": s.no_break_reason or "",
                "early_leave_reason": s.early_leave_reason or "",
                "scheduled_start": s.scheduled_start.strftime("%H:%M") if s.scheduled_start else None,
                "actual_start": s.actual_start.strftime("%H:%M") if s.actual_start else None,
                "scheduled_break_start": s.scheduled_break_start.strftime("%H:%M")
                if s.scheduled_break_start
                else None,
                "actual_break_start": s.actual_break_start.strftime("%H:%M")
                if s.actual_break_start
                else None,
                "scheduled_break_end": s.scheduled_break_end.strftime("%H:%M")
                if s.scheduled_break_end
                else None,
                "actual_break_end": s.actual_break_end.strftime("%H:%M")
                if s.actual_break_end
                else None,
                "scheduled_end": s.scheduled_end.strftime("%H:%M") if s.scheduled_end else None,
                "actual_end": s.actual_end.strftime("%H:%M") if s.actual_end else None,
                "break_minutes": s.break_minutes,
                "work_minutes": s.work_minutes,
                "span_minutes": s.span_minutes,
                "late_minutes": s.late_minutes,
                "early_leave_minutes": s.early_leave_minutes,
                "makeup_count": s.makeup_count,
                "is_absent": s.is_absent,
                "anomaly": s.anomaly_notes,
            }
        )
    return result


@router.get("/today")
def today_attendance(
    work_date: date | None = None,
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    d = work_date or today_local()
    q = db.query(AttendanceDailySummary).filter(AttendanceDailySummary.work_date == d)
    if store_id:
        q = q.filter(AttendanceDailySummary.store_id == store_id)
    # also include scheduled employees without summary yet
    from ..models import Schedule

    schedules = db.query(Schedule).filter(Schedule.work_date == d)
    if store_id:
        schedules = schedules.filter(Schedule.store_id == store_id)
    for sch in schedules.all():
        rebuild_daily_summary(db, sch.employee_id, d)
    rows = q.all() if store_id else db.query(AttendanceDailySummary).filter(
        AttendanceDailySummary.work_date == d
    ).all()
    if store_id:
        rows = (
            db.query(AttendanceDailySummary)
            .filter(AttendanceDailySummary.work_date == d, AttendanceDailySummary.store_id == store_id)
            .all()
        )
    out = []
    for s in rows:
        emp = db.query(Employee).filter(Employee.id == s.employee_id).first()
        out.append(
            {
                "employee_name": emp.name if emp else "",
                "work_date": str(s.work_date),
                "actual_start": s.actual_start.strftime("%H:%M") if s.actual_start else None,
                "actual_end": s.actual_end.strftime("%H:%M") if s.actual_end else None,
                "late_minutes": s.late_minutes,
                "is_absent": s.is_absent,
                "anomaly": s.anomaly_notes,
            }
        )
    return out


@router.get("/makeup")
def makeup_records(
    month: str | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    q = db.query(MakeupRecord)
    if user.role != "admin":
        q = q.filter(MakeupRecord.employee_id == user.id)
    elif employee_id:
        q = q.filter(MakeupRecord.employee_id == employee_id)
    if month:
        q = q.filter(MakeupRecord.month_key == month)
    rows = q.order_by(MakeupRecord.created_at.desc()).limit(500).all()
    labels = {
        "START": "上班",
        "BREAK_START": "開始休息",
        "BREAK_END": "結束休息",
        "END": "下班",
    }
    result = []
    for m in rows:
        emp = db.query(Employee).filter(Employee.id == m.employee_id).first()
        store = (
            db.query(Store).filter(Store.id == m.store_id).first()
            if m.store_id
            else (db.query(Store).filter(Store.id == emp.store_id).first() if emp else None)
        )
        result.append(
            {
                "id": m.id,
                "employee_name": emp.name if emp else "",
                "store_name": store.name if store else "",
                "work_date": str(m.work_date),
                "event_type": m.event_type,
                "event_label": labels.get(m.event_type, m.event_type),
                "missing_event": m.missing_event,
                "punched_at": m.punched_at.isoformat() if m.punched_at else None,
                "submitted_at": m.submitted_at.isoformat() if m.submitted_at else None,
                "reason": m.reason or "",
                "month_key": m.month_key,
                "sequence_in_month": m.sequence_in_month,
                "over_quota": m.over_quota,
                "warning_message": m.warning_message,
                "performance_flag": m.performance_flag,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return result


@router.get("/annual")
def annual_report(
    year: int = Query(...),
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    emps = db.query(Employee).filter(Employee.role == "employee")
    if store_id:
        emps = emps.filter(Employee.store_id == store_id)
    for e in emps.all():
        rebuild_annual(db, e.id, year)
    q = db.query(AnnualStatistic).filter(AnnualStatistic.year == year)
    if store_id:
        q = q.filter(AnnualStatistic.store_id == store_id)
    rows = q.all()
    out = []
    for a in rows:
        emp = db.query(Employee).filter(Employee.id == a.employee_id).first()
        store = db.query(Store).filter(Store.id == a.store_id).first()
        out.append(
            {
                "employee": emp.name if emp else "",
                "store": store.name if store else "",
                "year": a.year,
                "agreed_work_hours": round(a.agreed_work_minutes / 60, 2),
                "actual_work_hours": round(a.actual_work_minutes / 60, 2),
                "actual_span_hours": round(a.actual_span_minutes / 60, 2),
                "absent_hours": round(a.absent_minutes / 60, 2),
                "late_count": a.late_count,
                "late_hours": round(a.late_minutes / 60, 2),
                "early_leave_count": a.early_leave_count,
                "early_leave_hours": round(a.early_leave_minutes / 60, 2),
                "makeup_total": a.makeup_total,
                "makeup_over_quota": a.makeup_over_quota,
                "unscheduled_count": a.unscheduled_count,
                "unscheduled_hours": round(a.unscheduled_work_minutes / 60, 2),
                "no_break_count": a.no_break_count,
                "early_leave_reason_count": a.early_leave_reason_count,
            }
        )
    return out


@router.get("/employee/{employee_id}")
def get_employee_attendance(
    employee_id: int,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """員工只能看自己目前有效打卡；管理員可看任何人。不回傳 audit／修改歷史。"""
    if user.role != "admin" and user.id != employee_id:
        raise HTTPException(403, "不可查看其他員工資料")
    events = (
        db.query(AttendanceEvent)
        .filter(AttendanceEvent.employee_id == employee_id)
        .order_by(AttendanceEvent.punched_at.desc())
        .limit(100)
        .all()
    )
    # 員工端：僅目前有效時間；管理員可多看 is_makeup（來源標記，非修改歷史）
    out = []
    for e in events:
        row = {
            "work_date": str(e.work_date),
            "event_type": e.event_type,
            "punched_at": e.punched_at.isoformat(timespec="seconds"),
        }
        if user.role == "admin":
            row["is_makeup"] = e.is_makeup
        out.append(row)
    return out
