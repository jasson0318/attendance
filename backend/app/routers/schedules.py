from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin
from ..database import get_db
from ..models import Employee, Schedule
from ..schemas import DayOffRequest, ScheduleCreate

router = APIRouter(prefix="/api/schedules", tags=["schedules"])


@router.get("")
def list_schedules(
    year: int | None = None,
    month: int | None = None,
    store_id: int | None = None,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    q = db.query(Schedule)
    if user.role != "admin":
        q = q.filter(Schedule.employee_id == user.id)
    else:
        if store_id:
            q = q.filter(Schedule.store_id == store_id)
        if employee_id:
            q = q.filter(Schedule.employee_id == employee_id)
    if year and month:
        from calendar import monthrange

        last = monthrange(year, month)[1]
        q = q.filter(
            Schedule.work_date >= date(year, month, 1),
            Schedule.work_date <= date(year, month, last),
        )
    rows = q.order_by(Schedule.work_date).all()
    return [
        {
            "id": s.id,
            "employee_id": s.employee_id,
            "store_id": s.store_id,
            "work_date": str(s.work_date),
            "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
            "break_start": s.break_start.strftime("%H:%M") if s.break_start else None,
            "break_end": s.break_end.strftime("%H:%M") if s.break_end else None,
            "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
            "is_day_off": s.is_day_off,
            "source": s.source,
        }
        for s in rows
    ]


@router.post("")
def create_schedule(
    body: ScheduleCreate,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    existing = (
        db.query(Schedule)
        .filter(Schedule.employee_id == body.employee_id, Schedule.work_date == body.work_date)
        .first()
    )
    if existing:
        raise HTTPException(400, "該日已有排班")
    s = Schedule(
        employee_id=body.employee_id,
        store_id=body.store_id,
        work_date=body.work_date,
        start_time=body.start_time,
        break_start=body.break_start,
        break_end=body.break_end,
        end_time=body.end_time,
        is_day_off=body.is_day_off,
        shift_type="day_off" if body.is_day_off else "full_day",
        source="manual",
    )
    db.add(s)
    db.commit()
    return {"message": "已建立", "id": s.id}


@router.post("/day-off")
def set_day_off(
    body: DayOffRequest,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    emp = db.query(Employee).filter(Employee.id == body.employee_id).first()
    if not emp:
        raise HTTPException(404, "找不到員工")
    s = (
        db.query(Schedule)
        .filter(Schedule.employee_id == body.employee_id, Schedule.work_date == body.work_date)
        .first()
    )
    if not s:
        s = Schedule(
            employee_id=body.employee_id,
            store_id=emp.store_id,
            work_date=body.work_date,
        )
        db.add(s)
    s.is_day_off = body.is_day_off
    s.shift_type = "day_off" if body.is_day_off else "full_day"
    if body.is_day_off:
        s.start_time = s.break_start = s.break_end = s.end_time = None
    s.source = "manual"
    db.commit()
    return {"message": "已設定休假" if body.is_day_off else "已取消休假"}
