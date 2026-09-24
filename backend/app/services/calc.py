"""出勤計算邏輯：遲到、早退、休息補回、工作時數、曠職。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Optional


EVENT_TYPES = ("START", "BREAK_START", "BREAK_END", "END")


def combine(d: date, t: time) -> datetime:
    return datetime(d.year, d.month, d.day, t.hour, t.minute, t.second)


def minutes_between(a: datetime, b: datetime) -> int:
    return max(0, int((b - a).total_seconds() // 60))


@dataclass
class CalcSettings:
    late_grace_minutes: int = 5
    early_leave_grace_minutes: int = 5
    late_break_compensation: bool = True
    monthly_makeup_quota: int = 5  # -1 = unlimited


@dataclass
class ScheduleTimes:
    work_date: date
    start: Optional[time] = None
    break_start: Optional[time] = None
    break_end: Optional[time] = None
    end: Optional[time] = None
    is_day_off: bool = False
    has_schedule: bool = False


@dataclass
class PunchTimes:
    start: Optional[datetime] = None
    break_start: Optional[datetime] = None
    break_end: Optional[datetime] = None
    end: Optional[datetime] = None
    makeup_types: list[str] = field(default_factory=list)


@dataclass
class DailyResult:
    late_minutes: int = 0
    early_leave_minutes: int = 0
    break_minutes: int = 0
    work_minutes: int = 0
    span_minutes: int = 0
    makeup_count: int = 0
    is_absent: bool = False
    absent_minutes: int = 0
    anomaly_notes: str = ""
    attendance_status: str = "NO_SCHEDULE"
    effective_late_before_comp: int = 0
    compensated_late: int = 0
    scheduled_start: Optional[time] = None
    scheduled_break_start: Optional[time] = None
    scheduled_break_end: Optional[time] = None
    scheduled_end: Optional[time] = None


def calc_late_minutes(
    scheduled_start: time,
    actual_start: datetime,
    grace_minutes: int,
    work_date: Optional[date] = None,
) -> int:
    """
    遲到分鐘。寬限只影響判定，不改變排班時間。
    公式：max(0, 實際遲到分鐘 − 寬限)
    例：08:00 排班、寬限5 → 08:05=0、08:06=1、08:10=5
    """
    d = work_date or actual_start.date()
    scheduled_dt = combine(d, scheduled_start)
    raw = max(0, int((actual_start - scheduled_dt).total_seconds() // 60))
    return max(0, raw - grace_minutes)


def calc_early_leave_minutes(
    scheduled_end: time,
    actual_end: datetime,
    grace_minutes: int,
    work_date: Optional[date] = None,
) -> int:
    """
    早退分鐘。寬限只影響判定。
    例：17:00 下班、寬限5 → 16:55=0、16:54=1
    """
    d = work_date or actual_end.date()
    scheduled_dt = combine(d, scheduled_end)
    raw = max(0, int((scheduled_dt - actual_end).total_seconds() // 60))
    return max(0, raw - grace_minutes)


def calc_break_minutes(break_start: Optional[datetime], break_end: Optional[datetime]) -> int:
    if not break_start or not break_end or break_end <= break_start:
        return 0
    return minutes_between(break_start, break_end)


def calc_span_minutes(start: Optional[datetime], end: Optional[datetime]) -> int:
    if not start or not end or end <= start:
        return 0
    return minutes_between(start, end)


def calc_work_minutes(
    start: Optional[datetime],
    end: Optional[datetime],
    break_start: Optional[datetime],
    break_end: Optional[datetime],
) -> int:
    span = calc_span_minutes(start, end)
    brk = calc_break_minutes(break_start, break_end)
    return max(0, span - brk)


def apply_late_break_compensation(
    late_minutes: int,
    scheduled_break_minutes: int,
    actual_break_minutes: int,
    enabled: bool,
) -> tuple[int, int]:
    if not enabled or late_minutes <= 0:
        return late_minutes, 0
    shortened = max(0, scheduled_break_minutes - actual_break_minutes)
    compensated = min(late_minutes, shortened)
    return late_minutes - compensated, compensated


def count_missing_events(punch: PunchTimes, schedule: ScheduleTimes) -> list[str]:
    if not schedule.has_schedule or schedule.is_day_off:
        return []
    missing = []
    if schedule.start and not punch.start:
        missing.append("START")
    if schedule.break_start and not punch.break_start:
        missing.append("BREAK_START")
    if schedule.break_end and not punch.break_end:
        missing.append("BREAK_END")
    if schedule.end and not punch.end:
        missing.append("END")
    return missing


def is_absent(schedule: ScheduleTimes, punch: PunchTimes) -> bool:
    if not schedule.has_schedule or schedule.is_day_off:
        return False
    if not schedule.start:
        return False
    return not any([punch.start, punch.break_start, punch.break_end, punch.end])


def compute_daily(
    schedule: ScheduleTimes,
    punch: PunchTimes,
    settings: CalcSettings,
    agreed_daily_hours: float = 8.0,
) -> DailyResult:
    result = DailyResult(
        scheduled_start=schedule.start,
        scheduled_break_start=schedule.break_start,
        scheduled_break_end=schedule.break_end,
        scheduled_end=schedule.end,
        makeup_count=len(punch.makeup_types),
    )
    has_any_punch = any([punch.start, punch.break_start, punch.break_end, punch.end])

    # 無排班或休假：若有實際打卡 → 無排班出勤（不算曠職）
    if not schedule.has_schedule or schedule.is_day_off:
        result.break_minutes = calc_break_minutes(punch.break_start, punch.break_end)
        result.span_minutes = calc_span_minutes(punch.start, punch.end)
        result.work_minutes = calc_work_minutes(
            punch.start, punch.end, punch.break_start, punch.break_end
        )
        result.is_absent = False
        result.absent_minutes = 0
        if has_any_punch:
            result.attendance_status = "UNSCHEDULED_ATTENDANCE"
            result.anomaly_notes = "無排班出勤"
        elif schedule.is_day_off:
            result.attendance_status = "DAY_OFF"
            result.anomaly_notes = "休假"
        else:
            result.attendance_status = "NO_SCHEDULE"
            result.anomaly_notes = "無排班"
        return result

    notes: list[str] = []

    if schedule.start and punch.start:
        raw_late = calc_late_minutes(
            schedule.start, punch.start, settings.late_grace_minutes, schedule.work_date
        )
        result.effective_late_before_comp = raw_late
        result.late_minutes = raw_late
    elif schedule.start and not punch.start:
        notes.append("缺上班打卡")

    if schedule.end and punch.end:
        result.early_leave_minutes = calc_early_leave_minutes(
            schedule.end, punch.end, settings.early_leave_grace_minutes, schedule.work_date
        )
    elif schedule.end and not punch.end:
        notes.append("缺下班打卡")

    result.break_minutes = calc_break_minutes(punch.break_start, punch.break_end)
    result.span_minutes = calc_span_minutes(punch.start, punch.end)
    result.work_minutes = calc_work_minutes(
        punch.start, punch.end, punch.break_start, punch.break_end
    )

    if schedule.break_start and schedule.break_end:
        scheduled_break = minutes_between(
            combine(schedule.work_date, schedule.break_start),
            combine(schedule.work_date, schedule.break_end),
        )
    else:
        scheduled_break = 0

    if result.late_minutes > 0:
        effective, compensated = apply_late_break_compensation(
            result.late_minutes,
            scheduled_break,
            result.break_minutes,
            settings.late_break_compensation,
        )
        result.compensated_late = compensated
        result.late_minutes = effective

    result.is_absent = is_absent(schedule, punch)
    if result.is_absent:
        result.absent_minutes = int(agreed_daily_hours * 60)
        result.attendance_status = "ABSENT"
        notes.append("曠職")
    else:
        result.attendance_status = "NORMAL"

    missing = count_missing_events(punch, schedule)
    if missing and not result.is_absent:
        notes.append(f"漏打卡:{','.join(missing)}")

    result.anomaly_notes = ";".join(notes)
    return result


def makeup_warning_message(sequence: int, quota: int) -> Optional[str]:
    if quota < 0:
        return None
    if sequence <= quota:
        return None
    return (
        f"本月補打卡次數已超過公司設定的{quota}次。"
        f"本次為第{sequence}次補打卡，將列入年度考績審核紀錄。"
    )


def haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    from math import asin, cos, radians, sin, sqrt

    r = 6371000
    dlat = radians(lat2 - lat1)
    dlng = radians(lng2 - lng1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlng / 2) ** 2
    return 2 * r * asin(sqrt(a))
