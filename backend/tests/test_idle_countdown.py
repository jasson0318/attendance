"""閒置倒數顯示與同一 inactivity timer 同步。"""
from pathlib import Path

from backend.app.services.idle_policy import (
    IDLE_MS,
    LAST_ACTIVITY_KEY,
    WARN_BEFORE_MS,
    IdleTracker,
    format_mmss,
    remaining_ms,
    resolve_last_activity_on_start,
)

ROOT = Path(__file__).resolve().parents[2]
AUTH_JS = (ROOT / "frontend" / "static" / "js" / "auth_session.js").read_text(encoding="utf-8")
APP_JS = (ROOT / "frontend" / "static" / "js" / "app.js").read_text(encoding="utf-8")
INDEX = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
ADMIN = (ROOT / "frontend" / "admin.html").read_text(encoding="utf-8")


def test_login_display_starts_at_03_00():
    t = IdleTracker()
    t.activity(0)
    assert t.display(0) == "03:00"
    assert format_mmss(IDLE_MS) == "03:00"
    assert 'idle-countdown' in INDEX
    assert 'idle-countdown' in ADMIN
    assert "03:00" in INDEX


def test_countdown_each_second():
    t = IdleTracker()
    t.activity(0)
    assert t.display(1000) == "02:59"
    assert t.display(2000) == "02:58"
    assert t.display(IDLE_MS - WARN_BEFORE_MS) == "00:30"
    assert t.display(IDLE_MS - 1000) == "00:01"
    assert t.display(IDLE_MS) == "00:00"


def test_activity_resets_to_03_00():
    t = IdleTracker()
    t.activity(0)
    assert t.display(60_000) == "02:00"
    t.activity(60_000)
    assert t.display(60_000) == "03:00"


def test_warn_at_30_seconds():
    t = IdleTracker()
    t.activity(0)
    assert not t.should_warn(IDLE_MS - WARN_BEFORE_MS - 1)
    assert t.should_warn(IDLE_MS - WARN_BEFORE_MS)
    assert "您已閒置，30秒後將自動登出" in INDEX
    assert "warn" in AUTH_JS
    assert "⚠️" in AUTH_JS or "warn" in AUTH_JS


def test_continue_use_restores_03_00():
    t = IdleTracker()
    t.activity(0)
    t.should_warn(IDLE_MS - 10_000)
    t.mark_warn_shown()
    t.continue_use(IDLE_MS - 10_000)
    assert t.display(IDLE_MS - 10_000) == "03:00"
    assert "continueUse" in AUTH_JS
    assert "繼續使用" in INDEX


def test_zero_triggers_logout():
    t = IdleTracker()
    t.activity(0)
    assert not t.should_logout(IDLE_MS - 1)
    assert t.should_logout(IDLE_MS)


def test_countdown_uses_remaining_not_independent_decrement():
    """畫面倒數 = logoutAt - now，不是獨立 countdown--。"""
    last = 1_000_000
    now = last + 90_000
    assert remaining_ms(last, now) == IDLE_MS - 90_000
    assert format_mmss(remaining_ms(last, now)) == "01:30"
    assert "remainingMs" in AUTH_JS
    assert "LAST_ACTIVITY_KEY" in AUTH_JS
    assert "attendance_last_activity" in AUTH_JS


def test_refresh_does_not_wrongly_reset():
    now = 500_000
    stored = now - 60_000  # 已閒置 1 分鐘
    last, logout_now = resolve_last_activity_on_start(
        reset=False, now_ms=now, stored_ms=stored
    )
    assert logout_now is False
    assert last == stored
    assert remaining_ms(last, now) == IDLE_MS - 60_000
    assert format_mmss(remaining_ms(last, now)) == "02:00"

    # 剛登入才重設
    last2, logout2 = resolve_last_activity_on_start(
        reset=True, now_ms=now, stored_ms=stored
    )
    assert logout2 is False
    assert last2 == now
    assert remaining_ms(last2, now) == IDLE_MS

    assert "reset: !!loginData" in APP_JS or "reset:!!loginData" in APP_JS.replace(" ", "")
    assert "attendance_last_activity" in AUTH_JS
    assert LAST_ACTIVITY_KEY == "attendance_last_activity"


def test_expired_on_refresh_should_logout():
    now = 500_000
    stored = now - IDLE_MS - 1
    _last, logout_now = resolve_last_activity_on_start(
        reset=False, now_ms=now, stored_ms=stored
    )
    assert logout_now is True


def test_makeup_input_and_punch_confirm_are_activity():
    for ev in ("input", "keydown", "click", "touchstart", "pointerdown"):
        assert ev in AUTH_JS
    assert "makeup-reason" in APP_JS
    assert "openConfirm" in APP_JS
    assert "confirm-ok" in APP_JS


def test_touch_resets_idle():
    assert "touchstart" in AUTH_JS
    assert "touchmove" in AUTH_JS
    t = IdleTracker()
    t.activity(0)
    t.activity(100_000)  # 模擬觸控
    assert t.display(100_000) == "03:00"


def test_cross_tab_storage_sync_present():
    assert 'addEventListener("storage"' in AUTH_JS or "addEventListener('storage'" in AUTH_JS
    assert "LAST_ACTIVITY_KEY" in AUTH_JS
