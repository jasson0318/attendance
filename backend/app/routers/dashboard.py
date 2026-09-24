from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import (
    AttendanceDailySummary,
    AttendanceEvent,
    Employee,
    MakeupRecord,
    Schedule,
    Store,
)
from ..timeutil import today_local

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(db: Session = Depends(get_db), _: Employee = Depends(require_admin)):
    today = today_local()
    stores = db.query(Store).count()
    employees = db.query(Employee).filter(Employee.role == "employee", Employee.is_active == True).count()  # noqa: E712
    scheduled = db.query(Schedule).filter(Schedule.work_date == today, Schedule.is_day_off == False).count()  # noqa: E712
    punched_start = (
        db.query(AttendanceEvent)
        .filter(AttendanceEvent.work_date == today, AttendanceEvent.event_type == "START")
        .count()
    )
    absent = (
        db.query(AttendanceDailySummary)
        .filter(AttendanceDailySummary.work_date == today, AttendanceDailySummary.is_absent == True)  # noqa: E712
        .count()
    )
    month_key = today.strftime("%Y-%m")
    makeup_month = db.query(MakeupRecord).filter(MakeupRecord.month_key == month_key).count()
    over_quota = (
        db.query(MakeupRecord)
        .filter(MakeupRecord.month_key == month_key, MakeupRecord.over_quota == True)  # noqa: E712
        .count()
    )
    by_store = []
    for s in db.query(Store).order_by(Store.id).all():
        emp_c = db.query(Employee).filter(Employee.store_id == s.id, Employee.is_active == True).count()  # noqa: E712
        sch_c = db.query(Schedule).filter(Schedule.store_id == s.id, Schedule.work_date == today).count()
        by_store.append({"store": s.name, "employees": emp_c, "scheduled_today": sch_c})
    return {
        "date": str(today),
        "stores": stores,
        "active_employees": employees,
        "scheduled_today": scheduled,
        "punched_start_today": punched_start,
        "absent_today": absent,
        "makeup_this_month": makeup_month,
        "makeup_over_quota_this_month": over_quota,
        "by_store": by_store,
    }
