from datetime import date, datetime, time
from typing import Any, Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str
    employee_id: int


class StoreOut(BaseModel):
    id: int
    name: str
    code: str
    is_active: bool = True

    class Config:
        from_attributes = True


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None


class EmployeeCreate(BaseModel):
    name: str
    schedule_code: str
    store_id: int
    hire_date: Optional[date] = None
    leave_date: Optional[date] = None
    is_active: bool = True
    agreed_daily_hours: float = 8.0
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    username: str
    password: str
    role: str = "employee"


class EmployeeUpdate(BaseModel):
    name: Optional[str] = None
    schedule_code: Optional[str] = None
    store_id: Optional[int] = None
    hire_date: Optional[date] = None
    leave_date: Optional[date] = None
    is_active: Optional[bool] = None
    agreed_daily_hours: Optional[float] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    username: Optional[str] = None
    role: Optional[str] = None


class PasswordReset(BaseModel):
    password: str


class EmployeeOut(BaseModel):
    id: int
    name: str
    schedule_code: str
    store_id: int
    hire_date: Optional[date] = None
    leave_date: Optional[date] = None
    is_active: bool
    agreed_daily_hours: float
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    username: str
    role: str

    class Config:
        from_attributes = True


class PunchRequest(BaseModel):
    event_type: str
    is_makeup: bool = False
    punched_at: Optional[datetime] = None  # makeup claimed time
    work_date: Optional[date] = None
    reason: Optional[str] = None  # 補打卡原因（相容）
    makeup_reason: Optional[str] = None  # 補打卡原因
    unscheduled_reason: Optional[str] = None  # 無排班出勤原因
    punch_store_id: Optional[int] = None  # 實際打卡店舖（無排班可選）
    no_break_reason: Optional[str] = None  # 不休息直接下班原因
    early_leave_reason: Optional[str] = None  # 提前下班原因


class SettingsUpdate(BaseModel):
    late_grace_minutes: Optional[int] = None
    early_leave_grace_minutes: Optional[int] = None
    late_break_compensation: Optional[bool] = None
    monthly_makeup_quota: Optional[int] = None


class ScheduleCreate(BaseModel):
    employee_id: int
    store_id: int
    work_date: date
    start_time: Optional[time] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    end_time: Optional[time] = None
    is_day_off: bool = False


class DayOffRequest(BaseModel):
    employee_id: int
    work_date: date
    is_day_off: bool = True


class AdminEventUpdate(BaseModel):
    employee_id: int
    work_date: date
    event_type: str
    punched_at: datetime
    reason: Optional[str] = None


class AdminEventDelete(BaseModel):
    reason: Optional[str] = None


class AdminDayDelete(BaseModel):
    employee_id: int
    work_date: date
    reason: Optional[str] = None


class ApiMessage(BaseModel):
    message: str
    data: Optional[Any] = None
