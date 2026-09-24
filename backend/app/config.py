"""應用設定：環境變數優先，開發環境保持 SQLite 相容。"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# 可選載入專案根目錄 .env（不覆蓋已存在的環境變數）
_ENV_FILE = BASE_DIR / ".env"


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = val


_load_dotenv(_ENV_FILE)


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name, "true" if default else "false").lower()
    return raw in ("1", "true", "yes", "on")


APP_ENV = _env("APP_ENV", "development").lower()  # development | production
APP_TIMEZONE = _env("APP_TIMEZONE", "Asia/Taipei") or "Asia/Taipei"

# --- Database ---
_default_sqlite = f"sqlite:///{(DATA_DIR / 'attendance.sqlite3').as_posix()}"
DATABASE_URL = _env("DATABASE_URL", _default_sqlite) or _default_sqlite

# --- JWT / Auth ---
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(_env("ACCESS_TOKEN_EXPIRE_MINUTES", str(60 * 24 * 7)) or str(60 * 24 * 7))
IDLE_TIMEOUT_MINUTES = int(_env("IDLE_TIMEOUT_MINUTES", "3") or "3")
# 未來 server-side idle 用；目前與前端 3 分鐘無操作登出對齊，不改 UX
IDLE_TIMEOUT_MS = IDLE_TIMEOUT_MINUTES * 60 * 1000

# --- Server bind（開發／本機啟動腳本用，非 API 位址）---
HOST = _env("HOST", "0.0.0.0") or "0.0.0.0"
PORT = int(_env("PORT", "8800") or "8800")

# --- CORS（禁止 *）---
_DEFAULT_CORS = "http://127.0.0.1:8800,http://localhost:8800"


def _parse_cors_origins(raw: str) -> list[str]:
    parts = [p.strip() for p in (raw or "").split(",") if p.strip()]
    # 明確拒絕 wildcard
    return [p for p in parts if p != "*"]


CORS_ORIGINS = _parse_cors_origins(_env("CORS_ORIGINS", _DEFAULT_CORS) or _DEFAULT_CORS)
if not CORS_ORIGINS:
    CORS_ORIGINS = _parse_cors_origins(_DEFAULT_CORS)


def _load_secret_key() -> str:
    """
    優先序：
    1. SECRET_KEY
    2. ATTENDANCE_SECRET_KEY（相容舊名）
    3. 開發：data/.secret_key 或自動產生
    正式（APP_ENV=production）：必須提供環境變數，禁止靜默 fallback。
    """
    for name in ("SECRET_KEY", "ATTENDANCE_SECRET_KEY"):
        val = _env(name)
        if val:
            return val

    if APP_ENV in ("production", "prod"):
        raise RuntimeError(
            "正式環境必須設定環境變數 SECRET_KEY（或 ATTENDANCE_SECRET_KEY），"
            "不可使用自動產生的開發用金鑰。"
        )

    secret_file = DATA_DIR / ".secret_key"
    if secret_file.exists():
        existing = secret_file.read_text(encoding="utf-8").strip()
        if existing:
            return existing
    generated = secrets.token_urlsafe(48)
    secret_file.write_text(generated, encoding="utf-8")
    try:
        os.chmod(secret_file, 0o600)
    except OSError:
        pass
    return generated


SECRET_KEY = _load_secret_key()
