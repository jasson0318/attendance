"""初始化資料庫與預設資料。"""
from datetime import time

from sqlalchemy.orm import Session

from .auth import hash_password
from .models import Employee, Store
from .services.settings_service import ensure_defaults


def seed(db: Session) -> None:
    ensure_defaults(db)

    if db.query(Store).count() == 0:
        for i in range(1, 5):
            db.add(Store(name=f"店舖{i}", code=f"store{i}"))
        db.commit()

    if not db.query(Employee).filter(Employee.username == "admin").first():
        store1 = db.query(Store).filter(Store.code == "store1").first()
        db.add(
            Employee(
                name="系統管理員",
                schedule_code="ADMIN",
                store_id=store1.id,
                is_active=True,
                agreed_daily_hours=8.0,
                break_start=time(12, 0),
                break_end=time(13, 0),
                username="admin",
                password_hash=hash_password("admin123"),
                role="admin",
            )
        )
        db.commit()

    # 示範員工（可刪除）
    if not db.query(Employee).filter(Employee.username == "demo").first():
        store1 = db.query(Store).filter(Store.code == "store1").first()
        db.add(
            Employee(
                name="示範員工",
                schedule_code="傑",
                store_id=store1.id,
                is_active=True,
                agreed_daily_hours=8.0,
                break_start=time(12, 0),
                break_end=time(13, 0),
                username="demo",
                password_hash=hash_password("demo123"),
                role="employee",
            )
        )
        db.commit()
