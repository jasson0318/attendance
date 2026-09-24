from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import hash_password, require_admin
from ..database import get_db
from ..models import Employee
from ..schemas import EmployeeCreate, EmployeeOut, EmployeeUpdate, PasswordReset

router = APIRouter(prefix="/api/employees", tags=["employees"])


def _to_out(e: Employee) -> EmployeeOut:
    return EmployeeOut(
        id=e.id,
        name=e.name,
        schedule_code=e.schedule_code,
        store_id=e.store_id,
        hire_date=e.hire_date,
        leave_date=e.leave_date,
        is_active=e.is_active,
        agreed_daily_hours=e.agreed_daily_hours,
        break_start=e.break_start,
        break_end=e.break_end,
        username=e.username,
        role=e.role,
    )


@router.get("", response_model=list[EmployeeOut])
def list_employees(
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    q = db.query(Employee)
    if store_id:
        q = q.filter(Employee.store_id == store_id)
    return [_to_out(e) for e in q.order_by(Employee.id).all()]


@router.post("", response_model=EmployeeOut)
def create_employee(
    body: EmployeeCreate,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    if db.query(Employee).filter(Employee.username == body.username).first():
        raise HTTPException(400, "帳號已存在")
    e = Employee(
        name=body.name,
        schedule_code=body.schedule_code,
        store_id=body.store_id,
        hire_date=body.hire_date,
        leave_date=body.leave_date,
        is_active=body.is_active,
        agreed_daily_hours=body.agreed_daily_hours,
        break_start=body.break_start,
        break_end=body.break_end,
        username=body.username,
        password_hash=hash_password(body.password),
        role=body.role if body.role in ("admin", "employee") else "employee",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _to_out(e)


@router.get("/{employee_id}", response_model=EmployeeOut)
def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(404, "找不到員工")
    return _to_out(e)


@router.put("/{employee_id}", response_model=EmployeeOut)
def update_employee(
    employee_id: int,
    body: EmployeeUpdate,
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    from ..models import AuditLog

    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(404, "找不到員工")
    data = body.model_dump(exclude_unset=True)
    if "username" in data:
        exists = (
            db.query(Employee)
            .filter(Employee.username == data["username"], Employee.id != employee_id)
            .first()
        )
        if exists:
            raise HTTPException(400, "帳號已存在")
    changes = []
    for k, v in data.items():
        old = getattr(e, k)
        if old != v:
            changes.append(f"{k}:{old}->{v}")
            setattr(e, k, v)
    if changes:
        db.add(
            AuditLog(
                actor_id=admin.id,
                action="update_employee",
                detail=f"admin={admin.username};employee_id={e.id};changes={';'.join(changes)}",
            )
        )
    db.commit()
    db.refresh(e)
    return _to_out(e)


@router.post("/{employee_id}/reset-password")
def reset_password(
    employee_id: int,
    body: PasswordReset,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    e = db.query(Employee).filter(Employee.id == employee_id).first()
    if not e:
        raise HTTPException(404, "找不到員工")
    e.password_hash = hash_password(body.password)
    db.commit()
    return {"message": "密碼已重設"}
