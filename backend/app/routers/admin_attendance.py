"""管理員出勤事件管理：查看／修改／刪除（含 audit + 重算）。"""
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import AttendanceEvent, AuditLog, Employee, Schedule, Store
from ..schemas import AdminDayDelete, AdminEventUpdate
from ..services.calc import EVENT_TYPES
from ..services.summary_service import STATUS_LABELS, rebuild_annual, rebuild_daily_summary
from ..timeutil import today_local

router = APIRouter(prefix="/api/admin/attendance", tags=["admin-attendance"])

EVENT_LABELS = {
    "START": "上班",
    "BREAK_START": "開始休息",
    "BREAK_END": "結束休息",
    "END": "下班",
}


def _audit(db: Session, admin: Employee, action: str, detail: str) -> None:
    db.add(AuditLog(actor_id=admin.id, action=action, detail=detail))


@router.get("/today")
def admin_today(
    work_date: date | None = None,
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    d = work_date or today_local()
    # 有排班或當日有打卡的員工
    emp_ids = set()
    q_sch = db.query(Schedule).filter(Schedule.work_date == d)
    if store_id:
        q_sch = q_sch.filter(Schedule.store_id == store_id)
    for s in q_sch.all():
        emp_ids.add(s.employee_id)
    q_ev = db.query(AttendanceEvent.employee_id).filter(AttendanceEvent.work_date == d)
    for (eid,) in q_ev.distinct().all():
        emp_ids.add(eid)

    emps = db.query(Employee).filter(Employee.id.in_(emp_ids) if emp_ids else False).all() if emp_ids else []
    if store_id:
        emps = [e for e in emps if e.store_id == store_id]

    out = []
    for emp in sorted(emps, key=lambda x: x.id):
        summary = rebuild_daily_summary(db, emp.id, d)
        events = (
            db.query(AttendanceEvent)
            .filter(AttendanceEvent.employee_id == emp.id, AttendanceEvent.work_date == d)
            .all()
        )
        by_type = {e.event_type: e for e in events}
        store = db.query(Store).filter(Store.id == emp.store_id).first()
        out.append(
            {
                "employee_id": emp.id,
                "employee_name": emp.name,
                "store_name": store.name if store else "",
                "work_date": str(d),
                "actual_start": summary.actual_start.strftime("%H:%M") if summary.actual_start else None,
                "actual_break_start": summary.actual_break_start.strftime("%H:%M")
                if summary.actual_break_start
                else None,
                "actual_break_end": summary.actual_break_end.strftime("%H:%M")
                if summary.actual_break_end
                else None,
                "actual_end": summary.actual_end.strftime("%H:%M") if summary.actual_end else None,
                "late_minutes": summary.late_minutes,
                "early_leave_minutes": summary.early_leave_minutes,
                "attendance_status": summary.attendance_status,
                "attendance_status_label": STATUS_LABELS.get(
                    summary.attendance_status or "", summary.attendance_status or ""
                ),
                "event_count": len(by_type),
            }
        )
    return out


@router.get("/day-detail")
def day_detail(
    employee_id: int = Query(...),
    work_date: date = Query(...),
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.id == employee_id).first()
    if not emp:
        raise HTTPException(404, "找不到員工")
    summary = rebuild_daily_summary(db, employee_id, work_date)
    events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == employee_id,
            AttendanceEvent.work_date == work_date,
        )
        .all()
    )
    by_type = {e.event_type: e for e in events}
    event_list = []
    for t in EVENT_TYPES:
        e = by_type.get(t)
        event_list.append(
            {
                "event_type": t,
                "event_label": EVENT_LABELS[t],
                "exists": e is not None,
                "id": e.id if e else None,
                "punched_at": e.punched_at.isoformat(timespec="seconds") if e else None,
                "display_time": e.punched_at.strftime("%H:%M") if e else None,
                "is_makeup": e.is_makeup if e else False,
            }
        )
    return {
        "employee_id": emp.id,
        "employee_name": emp.name,
        "work_date": str(work_date),
        "attendance_status": summary.attendance_status,
        "attendance_status_label": STATUS_LABELS.get(
            summary.attendance_status or "", summary.attendance_status or ""
        ),
        "late_minutes": summary.late_minutes,
        "early_leave_minutes": summary.early_leave_minutes,
        "work_minutes": summary.work_minutes,
        "span_minutes": summary.span_minutes,
        "break_minutes": summary.break_minutes,
        "events": event_list,
    }


@router.put("/events")
def upsert_event(
    body: AdminEventUpdate,
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    if body.event_type not in EVENT_TYPES:
        raise HTTPException(400, "無效的打卡類型")
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(404, "找不到員工")

    event = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == body.employee_id,
            AttendanceEvent.work_date == body.work_date,
            AttendanceEvent.event_type == body.event_type,
        )
        .first()
    )
    old_time = event.punched_at.isoformat(timespec="seconds") if event else None
    action = "update_punch" if event else "create_punch"

    if event:
        event.punched_at = body.punched_at
        event.updated_at = datetime.utcnow()
    else:
        event = AttendanceEvent(
            employee_id=body.employee_id,
            store_id=emp.store_id,
            work_date=body.work_date,
            event_type=body.event_type,
            punched_at=body.punched_at,
            is_makeup=False,
        )
        db.add(event)

    _audit(
        db,
        admin,
        action,
        (
            f"admin={admin.username};employee_id={emp.id};employee={emp.name};"
            f"date={body.work_date};event={body.event_type};"
            f"original={old_time};new={body.punched_at.isoformat(timespec='seconds')};"
            f"reason={body.reason or ''}"
        ),
    )
    db.commit()

    summary = rebuild_daily_summary(db, body.employee_id, body.work_date)
    rebuild_annual(db, body.employee_id, body.work_date.year)
    return {
        "message": "已更新打卡",
        "event_id": event.id,
        "late_minutes": summary.late_minutes,
        "early_leave_minutes": summary.early_leave_minutes,
        "work_minutes": summary.work_minutes,
        "span_minutes": summary.span_minutes,
    }


@router.delete("/events/{event_id}")
def delete_event(
    event_id: int,
    reason: str | None = Query(None),
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    event = db.query(AttendanceEvent).filter(AttendanceEvent.id == event_id).first()
    if not event:
        raise HTTPException(404, "找不到打卡事件")
    emp = db.query(Employee).filter(Employee.id == event.employee_id).first()
    work_date = event.work_date
    employee_id = event.employee_id

    _audit(
        db,
        admin,
        "delete_punch",
        (
            f"admin={admin.username};employee_id={employee_id};"
            f"employee={emp.name if emp else ''};date={work_date};"
            f"event={event.event_type};original={event.punched_at.isoformat(timespec='seconds')};"
            f"reason={reason or ''}"
        ),
    )
    db.delete(event)
    db.commit()

    rebuild_daily_summary(db, employee_id, work_date)
    rebuild_annual(db, employee_id, work_date.year)
    return {"message": "已刪除打卡"}


@router.post("/day-delete")
def delete_day_events(
    body: AdminDayDelete,
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(404, "找不到員工")
    events = (
        db.query(AttendanceEvent)
        .filter(
            AttendanceEvent.employee_id == body.employee_id,
            AttendanceEvent.work_date == body.work_date,
        )
        .all()
    )
    if not events:
        return {"message": "當日無打卡可刪除", "deleted": 0}

    originals = [
        f"{e.event_type}:{e.punched_at.isoformat(timespec='seconds')}" for e in events
    ]
    _audit(
        db,
        admin,
        "delete_all_punches",
        (
            f"admin={admin.username};employee_id={emp.id};employee={emp.name};"
            f"date={body.work_date};deleted={','.join(originals)};"
            f"reason={body.reason or ''}"
        ),
    )
    for e in events:
        db.delete(e)
    db.commit()

    rebuild_daily_summary(db, body.employee_id, body.work_date)
    rebuild_annual(db, body.employee_id, body.work_date.year)
    return {"message": f"已刪除 {len(events)} 筆打卡", "deleted": len(events)}


def _parse_audit_detail(detail: str | None) -> dict:
    data = {}
    if not detail:
        return data
    for part in detail.split(";"):
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        data[k.strip()] = v.strip()
    return data


ACTION_LABELS = {
    "update_punch": "修改打卡",
    "create_punch": "建立打卡",
    "delete_punch": "刪除打卡",
    "delete_all_punches": "全部刪除當日打卡",
    "update_employee": "修改員工",
    "makeup_punch": "補打卡",
    "unscheduled_attendance": "無排班出勤",
}


@router.get("/audit-logs")
def list_audit_logs(
    employee_id: int | None = None,
    work_date: date | None = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    """僅管理員可查看操作歷史。"""
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    rows = q.limit(limit * 3).all()  # 先多取再過濾 detail
    out = []
    for row in rows:
        parsed = _parse_audit_detail(row.detail)
        if employee_id is not None and str(parsed.get("employee_id", "")) != str(employee_id):
            continue
        if work_date is not None and parsed.get("date") not in (str(work_date), None):
            # 若有 date 欄位則比對；無 date（如改員工）則略過日期過濾以外的也保留？規格要依員工+日期
            if "date" in parsed and parsed.get("date") != str(work_date):
                continue
            if "date" not in parsed:
                continue
        admin = db.query(Employee).filter(Employee.id == row.actor_id).first()
        out.append(
            {
                "id": row.id,
                "created_at": row.created_at.isoformat(timespec="seconds") if row.created_at else None,
                "admin_name": admin.name if admin else parsed.get("admin", ""),
                "admin_username": admin.username if admin else parsed.get("admin", ""),
                "action": row.action,
                "action_label": ACTION_LABELS.get(row.action, row.action),
                "employee_id": parsed.get("employee_id"),
                "employee_name": parsed.get("employee", ""),
                "work_date": parsed.get("date"),
                "event_type": parsed.get("event"),
                "event_label": EVENT_LABELS.get(parsed.get("event", ""), parsed.get("event", "")),
                "original_time": parsed.get("original"),
                "new_time": parsed.get("new"),
                "deleted": parsed.get("deleted"),
                "reason": parsed.get("reason", ""),
                "detail": row.detail,
            }
        )
        if len(out) >= limit:
            break
    return out
