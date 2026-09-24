"""系統設定讀寫。"""
from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import Setting
from .calc import CalcSettings

DEFAULTS = {
    "late_grace_minutes": "5",
    "early_leave_grace_minutes": "5",
    "late_break_compensation": "true",
    "monthly_makeup_quota": "5",
}

# 已停用現場驗證後不再使用的設定鍵（migration 會清除）
REMOVED_SETTING_KEYS = (
    "require_gps",
    "require_wifi",
    "wifi_verification_mode",
    "require_biometrics",
)


def ensure_defaults(db: Session) -> None:
    for k, v in DEFAULTS.items():
        if not db.query(Setting).filter(Setting.key == k).first():
            db.add(Setting(key=k, value=v))
    db.commit()


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.query(Setting).filter(Setting.key == key).first()
    return row.value if row else DEFAULTS.get(key, default)


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.query(Setting).filter(Setting.key == key).first()
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))
    db.commit()


def get_all_settings(db: Session) -> dict:
    ensure_defaults(db)
    rows = db.query(Setting).all()
    data = {r.key: r.value for r in rows}
    return {
        "late_grace_minutes": int(data.get("late_grace_minutes", 5)),
        "early_leave_grace_minutes": int(data.get("early_leave_grace_minutes", 5)),
        "late_break_compensation": data.get("late_break_compensation", "true").lower()
        == "true",
        "monthly_makeup_quota": int(data.get("monthly_makeup_quota", 5)),
    }


def get_calc_settings(db: Session) -> CalcSettings:
    s = get_all_settings(db)
    return CalcSettings(
        late_grace_minutes=s["late_grace_minutes"],
        early_leave_grace_minutes=s["early_leave_grace_minutes"],
        late_break_compensation=s["late_break_compensation"],
        monthly_makeup_quota=s["monthly_makeup_quota"],
    )
