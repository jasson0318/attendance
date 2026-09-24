"""每日出勤彙總與年度統計。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy.orm import Session

from ..models import (
    AnnualStatistic,
    AttendanceDailySummary,
    AttendanceEvent,
    Employee,
    MakeupRecord,
    Schedule,
    UnscheduledAttendance,
)
from .calc import (
    CalcSettings,
    PunchTimes,
    ScheduleTimes,
    compute_daily,
)
from .settings_service import get_calc_settings


def _punch_from_events(events: list[AttendanceEvent]) -> PunchTimes:
    punch = PunchTimes()
    makeup = []
    for e in events:
        if e.event_type == "START":
            punch.start = e.punched_at
        elif e.event_type == "BREAK_START":
            punch.break_start = e.punched_at
        elif e.event_type == "BREAK_END":
            punch.break_end = e.punched_at
        elif e.event_type == "END":
            punch.end = e.punched_at
        if e.is_makeup:
            makeup.append(e.event_type)
    punch.makeup_types = makeup
    return punch


def _schedule_times(sched: Optional[Schedule], work_date: date) -> ScheduleTimes:
    if not sched:
        return ScheduleTimes(work_date=work_date, has_schedule=False)
    return ScheduleTimes(
        work_date=work_date,
        start=sched.start_time,
        break_start=sched.break_start,
        break_end=sched.break_end,
        end=sched.end_time,
        is_day_off=sched.is_day_off,
        has_schedule=True,
    )


STATUS_LABELS = {
    "NORMAL": "正常出勤",
    "UNSCHEDULED_ATTENDANCE": "無排班出勤",
    "ABSENT": "曠職",
    "DAY_OFF": "休假",
    "NO_SCHEDULE": "無排班",
}


def rebuild_daily_summary(
    db: Session,
    employee_id: int,
    work_date: date,
    settings: Optional[CalcSettings] = None,
) -> AttendanceDailySummary:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ValueError("employee not found")
    settings = settings or get_calc_settings(db)
    sched = (
        db.query(Schedule)
        .filter(Schedule.employee_id == employee_id, Schedule.work_date == work_date)
        .first()
    )
    events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == employee_id,
            AttendanceEvent.work_date == work_date,
        )
        .all()
    )
    unscheduled = (
        db.query(UnscheduledAttendance)
        .filter(
            UnscheduledAttendance.employee_id == employee_id,
            UnscheduledAttendance.work_date == work_date,
        )
        .first()
    )
    st = _schedule_times(sched, work_date)
    punch = _punch_from_events(events)
    result = compute_daily(st, punch, settings, emp.agreed_daily_hours)

    # 若有無排班出勤紀錄，強制狀態
    if unscheduled and result.attendance_status != "ABSENT":
        result.attendance_status = "UNSCHEDULED_ATTENDANCE"
        result.is_absent = False
        result.absent_minutes = 0
        if not result.anomaly_notes or result.anomaly_notes in ("無排班", "休假"):
            result.anomaly_notes = "無排班出勤"

    row = (
        db.query(AttendanceDailySummary)
        .filter(
            AttendanceDailySummary.employee_id == employee_id,
            AttendanceDailySummary.work_date == work_date,
        )
        .first()
    )
    if not row:
        row = AttendanceDailySummary(
            employee_id=employee_id,
            store_id=emp.store_id,
            work_date=work_date,
        )
        db.add(row)

    punch_store_id = unscheduled.punch_store_id if unscheduled else emp.store_id
    if events:
        punch_store_id = events[0].store_id

    row.store_id = punch_store_id
    row.scheduled_start = result.scheduled_start
    row.actual_start = punch.start
    row.scheduled_break_start = result.scheduled_break_start
    row.actual_break_start = punch.break_start
    row.scheduled_break_end = result.scheduled_break_end
    row.actual_break_end = punch.break_end
    row.scheduled_end = result.scheduled_end
    row.actual_end = punch.end
    row.break_minutes = result.break_minutes
    row.work_minutes = result.work_minutes
    row.span_minutes = result.span_minutes
    row.late_minutes = result.late_minutes
    row.early_leave_minutes = result.early_leave_minutes
    row.makeup_count = result.makeup_count
    row.is_absent = result.is_absent
    row.absent_minutes = result.absent_minutes
    row.anomaly_notes = result.anomaly_notes
    row.is_day_off = st.is_day_off
    row.has_schedule = st.has_schedule and not st.is_day_off
    row.attendance_status = result.attendance_status
    row.unscheduled_reason = unscheduled.unscheduled_reason if unscheduled else None
    row.home_store_id = unscheduled.home_store_id if unscheduled else emp.store_id
    row.punch_store_id = punch_store_id
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row


def rebuild_annual(db: Session, employee_id: int, year: int) -> AnnualStatistic:
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise ValueError("employee not found")

    start = date(year, 1, 1)
    end = date(year, 12, 31)
    summaries = (
        db.query(AttendanceDailySummary)
        .filter(
            AttendanceDailySummary.employee_id == employee_id,
            AttendanceDailySummary.work_date >= start,
            AttendanceDailySummary.work_date <= end,
        )
        .all()
    )
    makeups = (
        db.query(MakeupRecord)
        .filter(
            MakeupRecord.employee_id == employee_id,
            MakeupRecord.month_key.like(f"{year}-%"),
        )
        .all()
    )

    agreed = 0
    for s in summaries:
        if s.has_schedule and not s.is_day_off:
            agreed += int(emp.agreed_daily_hours * 60)

    actual_work = sum(s.work_minutes for s in summaries if not s.is_absent)
    actual_span = sum(s.span_minutes for s in summaries if not s.is_absent)
    absent = sum(s.absent_minutes for s in summaries)
    late_rows = [s for s in summaries if s.late_minutes > 0]
    early_rows = [s for s in summaries if s.early_leave_minutes > 0]
    unscheduled_rows = [
        s for s in summaries if s.attendance_status == "UNSCHEDULED_ATTENDANCE"
    ]
    no_break_rows = [s for s in summaries if s.no_break_reason]
    early_reason_rows = [s for s in summaries if s.early_leave_reason]

    row = (
        db.query(AnnualStatistic)
        .filter(AnnualStatistic.employee_id == employee_id, AnnualStatistic.year == year)
        .first()
    )
    if not row:
        row = AnnualStatistic(employee_id=employee_id, store_id=emp.store_id, year=year)
        db.add(row)

    row.store_id = emp.store_id
    row.agreed_work_minutes = agreed
    row.actual_work_minutes = actual_work
    row.actual_span_minutes = actual_span
    row.absent_minutes = absent
    row.late_count = len(late_rows)
    row.late_minutes = sum(s.late_minutes for s in late_rows)
    row.early_leave_count = len(early_rows)
    row.early_leave_minutes = sum(s.early_leave_minutes for s in early_rows)
    row.makeup_total = len(makeups)
    row.makeup_over_quota = sum(1 for m in makeups if m.over_quota)
    row.unscheduled_count = len(unscheduled_rows)
    row.unscheduled_work_minutes = sum(s.work_minutes for s in unscheduled_rows)
    row.no_break_count = len(no_break_rows)
    row.early_leave_reason_count = len(early_reason_rows)
    row.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(row)
    return row
