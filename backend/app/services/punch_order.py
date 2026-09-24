"""正常打卡順序與例外（未休息／提前下班）防呆。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional

EVENT_LABELS = {
    "START": "上班打卡",
    "BREAK_START": "開始休息",
    "BREAK_END": "結束休息",
    "END": "下班打卡",
}

DONE_MESSAGES = {
    "START": "上班打卡已完成。",
    "BREAK_START": "開始休息已完成。",
    "BREAK_END": "結束休息已完成。",
    "END": "下班打卡已完成。",
}


@dataclass
class PunchOrderResult:
    ok: bool
    error: Optional[str] = None
    needs_no_break_reason: bool = False
    needs_early_leave_reason: bool = False


def done_set(events: list) -> set[str]:
    return {e.event_type if hasattr(e, "event_type") else e for e in events}


def is_before_scheduled_end(now: datetime, scheduled_end: Optional[time], work_date: date) -> bool:
    """實際下班時間是否早於排班下班（與早退寬限無關）。"""
    if scheduled_end is None:
        return False
    scheduled_dt = datetime.combine(work_date, scheduled_end)
    return now < scheduled_dt


def allowed_buttons(done: set[str]) -> dict[str, bool]:
    """前端按鈕啟用狀態（正常打卡）。"""
    if "END" in done:
        return {t: False for t in ("START", "BREAK_START", "BREAK_END", "END")}
    start = "START" in done
    bs = "BREAK_START" in done
    be = "BREAK_END" in done
    return {
        "START": not start,
        "BREAK_START": start and not bs and not be,
        "BREAK_END": bs and not be,
        # START 後可 END（不休息）；若已開始休息則必須先結束休息
        "END": start and (not bs or be) and "END" not in done,
    }


def preview_end_requirements(
    done: set[str],
    *,
    scheduled_end: Optional[time],
    now: datetime,
    work_date: date,
) -> tuple[bool, bool]:
    """點 END 前：是否需要未休息原因／提前下班原因。"""
    needs_no_break = "START" in done and "BREAK_START" not in done and "BREAK_END" not in done
    needs_early = is_before_scheduled_end(now, scheduled_end, work_date)
    return needs_no_break, needs_early


def validate_normal_punch(
    event_type: str,
    done: set[str],
    *,
    now: datetime,
    work_date: date,
    scheduled_end: Optional[time] = None,
    no_break_reason: Optional[str] = None,
    early_leave_reason: Optional[str] = None,
) -> PunchOrderResult:
    """驗證正常打卡（不含補打卡／管理員修改）。"""
    if event_type in done:
        return PunchOrderResult(ok=False, error=DONE_MESSAGES.get(event_type, "此打卡事件已完成"))

    if event_type == "START":
        return PunchOrderResult(ok=True)

    if event_type == "BREAK_START":
        if "START" not in done:
            return PunchOrderResult(ok=False, error="請先完成上班打卡。")
        return PunchOrderResult(ok=True)

    if event_type == "BREAK_END":
        if "BREAK_START" not in done:
            return PunchOrderResult(ok=False, error="請先完成開始休息打卡。")
        return PunchOrderResult(ok=True)

    if event_type == "END":
        if "START" not in done:
            return PunchOrderResult(ok=False, error="請先完成上班打卡。")
        # 已開始休息但尚未結束 → 不可直接下班
        if "BREAK_START" in done and "BREAK_END" not in done:
            return PunchOrderResult(ok=False, error="請先完成結束休息打卡。")

        needs_no_break = "BREAK_START" not in done and "BREAK_END" not in done
        needs_early = is_before_scheduled_end(now, scheduled_end, work_date)

        if needs_no_break and not (no_break_reason or "").strip():
            return PunchOrderResult(
                ok=False,
                error="請填寫未休息原因。",
                needs_no_break_reason=True,
                needs_early_leave_reason=needs_early,
            )
        if needs_early and not (early_leave_reason or "").strip():
            return PunchOrderResult(
                ok=False,
                error="您目前尚未到排班下班時間，請說明提前下班原因。",
                needs_no_break_reason=needs_no_break,
                needs_early_leave_reason=True,
            )
        return PunchOrderResult(
            ok=True,
            needs_no_break_reason=needs_no_break,
            needs_early_leave_reason=needs_early,
        )

    return PunchOrderResult(ok=False, error="無效的打卡類型")
