from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import (
    AttendanceDailySummary,
    AttendanceEvent,
    AuditLog,
    Employee,
    MakeupRecord,
    Schedule,
    Store,
    UnscheduledAttendance,
)
from ..schemas import PunchRequest
from ..services.calc import EVENT_TYPES, makeup_warning_message
from ..services.punch_order import (
    EVENT_LABELS,
    allowed_buttons,
    done_set,
    preview_end_requirements,
    validate_normal_punch,
)
from ..services.settings_service import get_all_settings, get_calc_settings
from ..services.summary_service import STATUS_LABELS, rebuild_annual, rebuild_daily_summary
from ..timeutil import now_naive_local, today_local

router = APIRouter(prefix="/api/punch", tags=["punch"])


def _is_unscheduled_day(sched: Schedule | None) -> bool:
    return sched is None or bool(sched.is_day_off)


def _today_view(db: Session, user: Employee, work_date: date) -> dict:
    now = now_naive_local()
    sched = (
        db.query(Schedule)
        .filter(Schedule.employee_id == user.id, Schedule.work_date == work_date)
        .first()
    )
    events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == user.id,
            AttendanceEvent.work_date == work_date,
        )
        .all()
    )
    done = {e.event_type: e for e in events}
    done_types = set(done.keys())
    settings = get_calc_settings(db)
    month_key = today_local().strftime("%Y-%m")
    makeup_count = (
        db.query(MakeupRecord)
        .filter(MakeupRecord.employee_id == user.id, MakeupRecord.month_key == month_key)
        .count()
    )
    store = db.query(Store).filter(Store.id == user.store_id).first()
    unscheduled = (
        db.query(UnscheduledAttendance)
        .filter(
            UnscheduledAttendance.employee_id == user.id,
            UnscheduledAttendance.work_date == work_date,
        )
        .first()
    )
    summary = (
        db.query(AttendanceDailySummary)
        .filter(
            AttendanceDailySummary.employee_id == user.id,
            AttendanceDailySummary.work_date == work_date,
        )
        .first()
    )
    needs_unscheduled_reason = _is_unscheduled_day(sched) and unscheduled is None
    stores = db.query(Store).filter(Store.is_active == True).order_by(Store.id).all()  # noqa: E712
    scheduled_end = sched.end_time if sched and not sched.is_day_off else None
    needs_no_break, needs_early = preview_end_requirements(
        done_types, scheduled_end=scheduled_end, now=now, work_date=work_date
    )
    no_break_reason = summary.no_break_reason if summary else None
    early_leave_reason = summary.early_leave_reason if summary else None

    def event_display(t: str) -> dict:
        if t in done:
            return {
                "done": True,
                "at": done[t].punched_at.strftime("%H:%M"),
                "label": EVENT_LABELS[t],
            }
        # 未休息下班：休息顯示「未休息」
        if t in ("BREAK_START", "BREAK_END") and no_break_reason and "END" in done:
            return {"done": False, "at": None, "label": "未休息", "skipped": True}
        return {"done": False, "at": None, "label": EVENT_LABELS[t]}

    return {
        "date": str(work_date),
        "server_time": now.strftime("%H:%M:%S"),
        "employee_name": user.name,
        "store_name": store.name if store else "",
        "home_store_id": user.store_id,
        "schedule": None
        if not sched
        else {
            "is_day_off": sched.is_day_off,
            "start": sched.start_time.strftime("%H:%M") if sched.start_time else None,
            "break_start": sched.break_start.strftime("%H:%M") if sched.break_start else None,
            "break_end": sched.break_end.strftime("%H:%M") if sched.break_end else None,
            "end": sched.end_time.strftime("%H:%M") if sched.end_time else None,
        },
        "is_unscheduled_day": _is_unscheduled_day(sched),
        "needs_unscheduled_reason": needs_unscheduled_reason,
        "needs_no_break_reason": needs_no_break and "END" not in done_types,
        "needs_early_leave_reason": needs_early and "END" not in done_types,
        "no_break_reason": no_break_reason,
        "early_leave_reason": early_leave_reason,
        "allowed": allowed_buttons(done_types),
        "unscheduled": None
        if not unscheduled
        else {
            "reason": unscheduled.unscheduled_reason,
            "home_store_id": unscheduled.home_store_id,
            "punch_store_id": unscheduled.punch_store_id,
            "status": "UNSCHEDULED_ATTENDANCE",
            "status_label": STATUS_LABELS["UNSCHEDULED_ATTENDANCE"],
        },
        "events": {t: event_display(t) for t in EVENT_TYPES},
        "punch_enabled": True,
        "stores": [{"id": s.id, "name": s.name} for s in stores],
        "makeup": {
            "used": makeup_count,
            "quota": settings.monthly_makeup_quota,
            "allowed_anytime": True,
        },
        "settings": get_all_settings(db),
    }


@router.get("/today")
def punch_today(
    work_date: date | None = None,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    return _today_view(db, user, work_date or today_local())


@router.post("")
def do_punch(
    body: PunchRequest,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    if body.event_type not in EVENT_TYPES:
        raise HTTPException(400, "無效的打卡類型")

    work_date = body.work_date or today_local()
    submitted_at = now_naive_local()
    sched = (
        db.query(Schedule)
        .filter(Schedule.employee_id == user.id, Schedule.work_date == work_date)
        .first()
    )
    unscheduled_day = _is_unscheduled_day(sched)
    existing_unscheduled = (
        db.query(UnscheduledAttendance)
        .filter(
            UnscheduledAttendance.employee_id == user.id,
            UnscheduledAttendance.work_date == work_date,
        )
        .first()
    )

    if body.is_makeup:
        if not body.work_date:
            raise HTTPException(400, "補打卡需指定日期")
        makeup_reason = (body.makeup_reason or body.reason or "").strip()
        if not makeup_reason:
            raise HTTPException(400, "請填寫補打卡原因。")
    else:
        if unscheduled_day and body.event_type == "START" and not existing_unscheduled:
            ureason = (body.unscheduled_reason or "").strip()
            if not ureason:
                raise HTTPException(400, "今日沒有排班，請先填寫出勤原因。")
        if unscheduled_day and body.event_type != "START" and not existing_unscheduled:
            start_exists = (
                db.query(AttendanceEvent)
                .filter(
                    AttendanceEvent.employee_id == user.id,
                    AttendanceEvent.work_date == work_date,
                    AttendanceEvent.event_type == "START",
                )
                .first()
            )
            if not start_exists:
                raise HTTPException(400, "今日沒有排班，請先完成上班打卡並填寫出勤原因。")

    existing_events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == user.id,
            AttendanceEvent.work_date == work_date,
        )
        .all()
    )
    done = done_set(existing_events)

    existing = next((e for e in existing_events if e.event_type == body.event_type), None)
    if existing:
        if body.is_makeup:
            raise HTTPException(400, "此項目已有打卡紀錄，無需補打卡。")
        from ..services.punch_order import DONE_MESSAGES

        raise HTTPException(400, DONE_MESSAGES.get(body.event_type, "此打卡事件已完成"))

    order_result = None
    if not body.is_makeup:
        scheduled_end = sched.end_time if sched and not sched.is_day_off else None
        punched_for_order = submitted_at
        order_result = validate_normal_punch(
            body.event_type,
            done,
            now=punched_for_order,
            work_date=work_date,
            scheduled_end=scheduled_end,
            no_break_reason=body.no_break_reason,
            early_leave_reason=body.early_leave_reason,
        )
        if not order_result.ok:
            raise HTTPException(400, order_result.error)

    calc = get_calc_settings(db)

    # 打卡店舖：無排班可選實際店舖，其餘使用所屬門市（不做現場位置驗證）
    punch_store = db.query(Store).filter(Store.id == user.store_id).first()
    if body.punch_store_id:
        chosen = db.query(Store).filter(Store.id == body.punch_store_id, Store.is_active == True).first()  # noqa: E712
        if chosen:
            punch_store = chosen

    punched_at = body.punched_at if body.is_makeup and body.punched_at else submitted_at
    warning = None
    over_quota = False
    store_id = punch_store.id if punch_store else user.store_id

    if body.is_makeup:
        month_key = submitted_at.strftime("%Y-%m")
        used = (
            db.query(MakeupRecord)
            .filter(MakeupRecord.employee_id == user.id, MakeupRecord.month_key == month_key)
            .count()
        )
        sequence = used + 1
        warning = makeup_warning_message(sequence, calc.monthly_makeup_quota)
        over_quota = warning is not None
        makeup_reason = (body.makeup_reason or body.reason or "").strip()
        db.add(
            MakeupRecord(
                employee_id=user.id,
                store_id=user.store_id,
                work_date=work_date,
                event_type=body.event_type,
                missing_event=body.event_type,
                punched_at=punched_at,
                submitted_at=submitted_at,
                reason=makeup_reason,
                month_key=month_key,
                sequence_in_month=sequence,
                over_quota=over_quota,
                warning_message=warning,
                performance_flag=over_quota,
            )
        )
        db.add(
            AuditLog(
                actor_id=user.id,
                action="makeup_punch",
                detail=(
                    f"employee={user.id};store={user.store_id};date={work_date};"
                    f"event={body.event_type};punched_at={punched_at.isoformat()};"
                    f"submitted_at={submitted_at.isoformat()};makeup_reason={makeup_reason};"
                    f"seq={sequence};over_quota={over_quota}"
                ),
            )
        )

    if (
        not body.is_makeup
        and unscheduled_day
        and body.event_type == "START"
        and not existing_unscheduled
    ):
        ureason = (body.unscheduled_reason or "").strip()
        db.add(
            UnscheduledAttendance(
                employee_id=user.id,
                home_store_id=user.store_id,
                punch_store_id=store_id,
                work_date=work_date,
                unscheduled_reason=ureason,
                start_punched_at=punched_at,
            )
        )
        db.add(
            AuditLog(
                actor_id=user.id,
                action="unscheduled_attendance",
                detail=(
                    f"employee={user.id};home_store={user.store_id};punch_store={store_id};"
                    f"date={work_date};unscheduled_reason={ureason};"
                    f"start={punched_at.isoformat()}"
                ),
            )
        )

    event = AttendanceEvent(
        employee_id=user.id,
        store_id=store_id,
        work_date=work_date,
        event_type=body.event_type,
        punched_at=punched_at,
        is_makeup=body.is_makeup,
        gps_lat=None,
        gps_lng=None,
        gps_ok=None,
        wifi_ok=None,
        wifi_method=None,
        note=(body.makeup_reason or body.reason or "").strip() if body.is_makeup else None,
    )
    db.add(event)
    db.commit()

    summary = rebuild_daily_summary(db, user.id, work_date, calc)

    if not body.is_makeup and body.event_type == "END" and order_result:
        if order_result.needs_no_break_reason:
            summary.no_break_reason = (body.no_break_reason or "").strip()
        if order_result.needs_early_leave_reason:
            summary.early_leave_reason = (body.early_leave_reason or "").strip()
        if order_result.needs_no_break_reason or order_result.needs_early_leave_reason:
            db.commit()
            db.refresh(summary)
            notes = []
            if summary.no_break_reason:
                notes.append(f"未休息：{summary.no_break_reason}")
            if summary.early_leave_reason:
                notes.append(f"提前下班：{summary.early_leave_reason}")
            if notes:
                extra = "；".join(notes)
                if summary.anomaly_notes:
                    if extra not in summary.anomaly_notes:
                        summary.anomaly_notes = f"{summary.anomaly_notes}；{extra}"
                else:
                    summary.anomaly_notes = extra
                db.commit()

    rebuild_annual(db, user.id, work_date.year)

    return {
        "message": "補打卡成功" if body.is_makeup else "打卡成功",
        "event_type": body.event_type,
        "event_label": EVENT_LABELS.get(body.event_type, body.event_type),
        "punched_at": punched_at.isoformat(timespec="seconds"),
        "submitted_at": submitted_at.isoformat(timespec="seconds") if body.is_makeup else None,
        "warning": warning,
        "over_quota": over_quota,
        "attendance_status": "UNSCHEDULED_ATTENDANCE"
        if (unscheduled_day and not body.is_makeup)
        else None,
        "home_store_id": user.store_id,
        "punch_store_id": store_id,
        "today": _today_view(db, user, today_local()),
    }
