"""閒置登出策略（前後端共用語意，供測試驗證）。"""
from __future__ import annotations

import math

from ..config import IDLE_TIMEOUT_MS

IDLE_MS = int(IDLE_TIMEOUT_MS)
WARN_BEFORE_MS = 30 * 1000  # 到期前 30 秒提醒
LAST_ACTIVITY_KEY = "attendance_last_activity"

# 未來 Cloud：後端可依 IDLE_TIMEOUT_MINUTES + last_activity 強制失效 JWT；
# 目前仍由前端倒數結束後呼叫 /api/auth/logout 寫入 revoked_tokens（UX 不變）。


def remaining_ms(last_activity_ms: int, now_ms: int, idle_ms: int = IDLE_MS) -> int:
    """以 lastActivity + idle 計算真實剩餘毫秒（避免獨立 countdown--）。"""
    return max(0, idle_ms - max(0, now_ms - last_activity_ms))


def format_mmss(ms: int) -> str:
    """顯示用 MM:SS（向上取整秒）。"""
    secs = max(0, int(math.ceil(max(0, ms) / 1000.0)))
    minutes = secs // 60
    sec = secs % 60
    return f"{minutes:02d}:{sec:02d}"


def is_warn_remaining(remain_ms: int, warn_before_ms: int = WARN_BEFORE_MS) -> bool:
    return 0 < remain_ms <= warn_before_ms


def resolve_last_activity_on_start(
    *,
    reset: bool,
    now_ms: int,
    stored_ms: int | None,
    idle_ms: int = IDLE_MS,
) -> tuple[int, bool]:
    """
    啟動閒置監控時決定 last_activity。
    回傳 (last_activity_ms, should_logout_immediately)。
    - reset=True（剛登入）：重設為 now
    - reset=False（重新整理／換頁）：沿用 stored；已逾時則應立即登出
    """
    if reset or stored_ms is None:
        return now_ms, False
    if now_ms - stored_ms >= idle_ms:
        return stored_ms, True
    return stored_ms, False


class IdleTracker:
    def __init__(self, idle_ms: int = IDLE_MS, warn_before_ms: int = WARN_BEFORE_MS):
        self.idle_ms = idle_ms
        self.warn_before_ms = warn_before_ms
        self.last_activity_ms = 0
        self.warn_shown = False
        self._started = False

    def activity(self, now_ms: int) -> None:
        self.last_activity_ms = now_ms
        self.warn_shown = False
        self._started = True

    def elapsed(self, now_ms: int) -> int:
        return max(0, now_ms - self.last_activity_ms)

    def remaining(self, now_ms: int) -> int:
        return remaining_ms(self.last_activity_ms, now_ms, self.idle_ms)

    def display(self, now_ms: int) -> str:
        return format_mmss(self.remaining(now_ms))

    def should_warn(self, now_ms: int) -> bool:
        rem = self.remaining(now_ms)
        return is_warn_remaining(rem, self.warn_before_ms) and not self.warn_shown

    def mark_warn_shown(self) -> None:
        self.warn_shown = True

    def should_logout(self, now_ms: int) -> bool:
        return self._started and self.remaining(now_ms) <= 0

    def continue_use(self, now_ms: int) -> None:
        """點擊繼續使用：重置計時。"""
        self.activity(now_ms)
