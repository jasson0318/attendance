from datetime import date, datetime, time
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_radius_m: Mapped[int] = mapped_column(Integer, default=100)
    wifi_ssid: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    wifi_bssid: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    employees = relationship("Employee", back_populates="store")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    schedule_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    hire_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    leave_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    agreed_daily_hours: Mapped[float] = mapped_column(Float, default=8.0)
    break_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    break_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="employee")  # admin | employee
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    store = relationship("Store", back_populates="employees")


class Setting(Base):
    __tablename__ = "settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class Schedule(Base):
    __tablename__ = "schedules"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_employee_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    shift_type: Mapped[str] = mapped_column(String(20), default="full_day")  # full_day | day_off
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    break_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    break_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    is_day_off: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str] = mapped_column(String(50), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee")
    store = relationship("Store")


class AttendanceEvent(Base):
    __tablename__ = "attendance_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)  # START|BREAK_START|BREAK_END|END
    punched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_makeup: Mapped[bool] = mapped_column(Boolean, default=False)
    gps_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    gps_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    wifi_ok: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    wifi_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    employee = relationship("Employee")


class MakeupRecord(Base):
    __tablename__ = "makeup_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    store_id: Mapped[Optional[int]] = mapped_column(ForeignKey("stores.id"), nullable=True)
    work_date: Mapped[date] = mapped_column(Date, nullable=False)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False)
    missing_event: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    punched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    month_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)  # YYYY-MM
    sequence_in_month: Mapped[int] = mapped_column(Integer, nullable=False)
    over_quota: Mapped[bool] = mapped_column(Boolean, default=False)
    warning_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performance_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee")


class UnscheduledAttendance(Base):
    """無排班出勤紀錄（與補打卡原因完全分開）。"""

    __tablename__ = "unscheduled_attendances"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_unscheduled_employee_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    home_store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    punch_store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    unscheduled_reason: Mapped[str] = mapped_column(Text, nullable=False)
    start_punched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    employee = relationship("Employee")


class AttendanceDailySummary(Base):
    __tablename__ = "attendance_daily_summary"
    __table_args__ = (
        UniqueConstraint("employee_id", "work_date", name="uq_summary_employee_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    work_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    scheduled_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_break_start: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_break_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_break_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_break_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    scheduled_end: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    actual_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    break_minutes: Mapped[int] = mapped_column(Integer, default=0)
    work_minutes: Mapped[int] = mapped_column(Integer, default=0)
    span_minutes: Mapped[int] = mapped_column(Integer, default=0)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0)
    makeup_count: Mapped[int] = mapped_column(Integer, default=0)
    is_absent: Mapped[bool] = mapped_column(Boolean, default=False)
    absent_minutes: Mapped[int] = mapped_column(Integer, default=0)
    anomaly_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_day_off: Mapped[bool] = mapped_column(Boolean, default=False)
    has_schedule: Mapped[bool] = mapped_column(Boolean, default=False)
    attendance_status: Mapped[str] = mapped_column(String(40), default="NO_SCHEDULE")
    # NORMAL | UNSCHEDULED_ATTENDANCE | ABSENT | DAY_OFF | NO_SCHEDULE
    unscheduled_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    no_break_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    early_leave_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    home_store_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    punch_store_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AnnualStatistic(Base):
    __tablename__ = "annual_statistics"
    __table_args__ = (
        UniqueConstraint("employee_id", "year", name="uq_annual_employee_year"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False)
    store_id: Mapped[int] = mapped_column(ForeignKey("stores.id"), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    agreed_work_minutes: Mapped[int] = mapped_column(Integer, default=0)
    actual_work_minutes: Mapped[int] = mapped_column(Integer, default=0)
    actual_span_minutes: Mapped[int] = mapped_column(Integer, default=0)
    absent_minutes: Mapped[int] = mapped_column(Integer, default=0)
    late_count: Mapped[int] = mapped_column(Integer, default=0)
    late_minutes: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_count: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_minutes: Mapped[int] = mapped_column(Integer, default=0)
    makeup_total: Mapped[int] = mapped_column(Integer, default=0)
    makeup_over_quota: Mapped[int] = mapped_column(Integer, default=0)
    unscheduled_count: Mapped[int] = mapped_column(Integer, default=0)
    unscheduled_work_minutes: Mapped[int] = mapped_column(Integer, default=0)
    no_break_count: Mapped[int] = mapped_column(Integer, default=0)
    early_leave_reason_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RevokedToken(Base):
    """登出／閒置登出後失效的 JWT（jti）。"""

    __tablename__ = "revoked_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TokenActivity(Base):
    """JWT 活動追蹤（server-side idle timeout；寫入有節流）。"""

    __tablename__ = "token_activities"

    jti: Mapped[str] = mapped_column(String(64), primary_key=True)
    employee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    last_activity_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
