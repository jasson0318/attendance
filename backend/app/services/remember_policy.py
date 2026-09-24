"""記住帳密策略：僅安全保存帳號，絕不在本機儲存明碼密碼。"""
from __future__ import annotations

REMEMBER_USER_KEY = "attendance_remember_user"
REMEMBER_FLAG_KEY = "attendance_remember_flag"
# 明確禁止的密碼儲存鍵（任何實作都不應寫入）
FORBIDDEN_PASSWORD_KEYS = (
    "attendance_password",
    "attendance_remember_password",
    "password",
    "remember_password",
)


def apply_remember_preference(
    storage: dict,
    *,
    username: str,
    password: str,
    remember: bool,
) -> dict:
    """
    模擬前端記住帳密行為。
    - 勾選：只寫入帳號與旗標；密碼不得寫入 storage（交由 Credential API / 瀏覽器密碼管理）。
    - 未勾選：清除帳號與旗標。
    password 參數僅供呼叫端交給瀏覽器 API，此函式絕不寫入 storage。
    """
    _ = password  # 明確不使用於 storage
    for key in FORBIDDEN_PASSWORD_KEYS:
        storage.pop(key, None)

    if not remember:
        storage.pop(REMEMBER_USER_KEY, None)
        storage.pop(REMEMBER_FLAG_KEY, None)
        return {"remember": False, "username": None, "password_in_storage": False}

    storage[REMEMBER_FLAG_KEY] = "1"
    storage[REMEMBER_USER_KEY] = username
    return {
        "remember": True,
        "username": username,
        "password_in_storage": _password_leaked(storage),
    }


def load_remembered_username(storage: dict) -> str | None:
    if storage.get(REMEMBER_FLAG_KEY) != "1":
        return None
    return storage.get(REMEMBER_USER_KEY) or None


def _password_leaked(storage: dict) -> bool:
    for key, val in storage.items():
        kl = str(key).lower()
        if "pass" in kl and val:
            return True
    return False


def assert_no_plaintext_password(storage: dict) -> bool:
    return not _password_leaked(storage)
