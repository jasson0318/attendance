"""業務時區工具：正式業務時區固定為 Asia/Taipei（可由 APP_TIMEZONE 覆寫）。"""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from .config import APP_TIMEZONE


def tzinfo() -> ZoneInfo:
    return ZoneInfo(APP_TIMEZONE)


def now_local() -> datetime:
    """目前業務時間（aware，Asia/Taipei）。打卡／伺服器時間用此函式。"""
    return datetime.now(tzinfo())


def now_naive_local() -> datetime:
    """
    目前業務時間（naive，去掉 tzinfo）。
    與現有 SQLite DateTime（無時區）欄位相容；語意仍為台北時間。
    """
    return now_local().replace(tzinfo=None)


def today_local() -> date:
    """目前業務日期（Asia/Taipei）。"""
    return now_local().date()
