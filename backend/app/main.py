"""出勤打卡系統 - FastAPI 主程式"""
from datetime import datetime, timezone
from pathlib import Path
import logging

from zoneinfo import ZoneInfoNotFoundError

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from .config import APP_ENV, APP_TIMEZONE, CORS_ORIGINS, IDLE_TIMEOUT_MINUTES
from .database import Base, SessionLocal, engine
from .migrate import migrate_schema
from .routers import (
    admin_attendance,
    attendance,
    auth,
    dashboard,
    employees,
    excel_api,
    punch,
    schedules,
    settings,
    stores,
)
from .seed import seed
from .services import preview_store as _preview_store  # noqa: F401  — register ExcelPreviewBlob
from .timeutil import now_local

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("attendance")

_is_production = APP_ENV in ("production", "prod")
# production 不公開 Swagger / ReDoc / OpenAPI；development 維持 /docs
app = FastAPI(
    title="出勤打卡系統",
    description="Attendance System",
    version="1.0.0",
    docs_url=None if _is_production else "/docs",
    redoc_url=None if _is_production else "/redoc",
    openapi_url=None if _is_production else "/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "ngrok-skip-browser-warning"],
)

Base.metadata.create_all(bind=engine)
migrate_schema(engine)
with SessionLocal() as db:
    seed(db)

logger.info("startup env=%s timezone=%s cors=%s", APP_ENV, APP_TIMEZONE, CORS_ORIGINS)

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(stores.router)
app.include_router(schedules.router)
app.include_router(punch.router)
app.include_router(attendance.router)
app.include_router(admin_attendance.router)
app.include_router(settings.router)
app.include_router(excel_api.router)
app.include_router(dashboard.router)

FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
STATIC = FRONTEND / "static"
if STATIC.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC)), name="static")


@app.exception_handler(Exception)
async def unhandled_exception(request: Request, exc: Exception):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        raise exc
    logger.exception("unhandled error path=%s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "伺服器錯誤"})


@app.get("/")
def index():
    index_path = FRONTEND / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    payload = {"message": "出勤打卡系統 API"}
    if not _is_production:
        payload["docs"] = "/docs"
    return payload


@app.get("/admin")
@app.get("/admin.html")
def admin_page():
    path = FRONTEND / "admin.html"
    if path.exists():
        return FileResponse(path)
    return {"message": "admin UI missing"}


@app.get("/manifest.webmanifest")
def manifest():
    path = FRONTEND / "manifest.webmanifest"
    return FileResponse(path, media_type="application/manifest+json")


@app.get("/sw.js")
def service_worker():
    path = FRONTEND / "sw.js"
    return FileResponse(path, media_type="application/javascript")


def _health_timestamp() -> str:
    """健康檢查不應因 Windows 缺少 IANA tzdata 而整段 500。"""
    try:
        return now_local().isoformat()
    except ZoneInfoNotFoundError:
        logger.warning("health check: timezone data unavailable, using UTC timestamp")
        return datetime.now(timezone.utc).isoformat()


@app.get("/api/health")
@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "attendance",
        "timezone": APP_TIMEZONE,
        "idle_timeout_minutes": IDLE_TIMEOUT_MINUTES,
        "timestamp": _health_timestamp(),
    }


@app.get("/api/public-config")
def public_config():
    """前端可讀的非機密設定（不含 SECRET／DB 密碼）。"""
    return {
        "timezone": APP_TIMEZONE,
        "idle_timeout_minutes": IDLE_TIMEOUT_MINUTES,
    }
