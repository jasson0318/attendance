from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Employee
from ..schemas import SettingsUpdate
from ..services.settings_service import get_all_settings, set_setting

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def read_settings(db: Session = Depends(get_db), _: Employee = Depends(require_admin)):
    return get_all_settings(db)


@router.put("")
def update_settings(
    body: SettingsUpdate,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    data = body.model_dump(exclude_unset=True)
    mapping = {
        "late_grace_minutes": lambda v: str(int(v)),
        "early_leave_grace_minutes": lambda v: str(int(v)),
        "late_break_compensation": lambda v: "true" if v else "false",
        "monthly_makeup_quota": lambda v: str(int(v)),
    }
    # validate grace options
    if "late_grace_minutes" in data and data["late_grace_minutes"] not in (0, 5, 10, 15):
        return {"error": "遲到寬限僅允許 0/5/10/15"}
    if "early_leave_grace_minutes" in data and data["early_leave_grace_minutes"] not in (
        0,
        5,
        10,
        15,
    ):
        return {"error": "早退寬限僅允許 0/5/10/15"}
    if "monthly_makeup_quota" in data and data["monthly_makeup_quota"] not in (
        3,
        5,
        7,
        -1,
    ):
        return {"error": "月補打卡額度僅允許 3/5/7/-1(不限)"}

    for k, v in data.items():
        if k in mapping:
            set_setting(db, k, mapping[k](v))
    return get_all_settings(db)
