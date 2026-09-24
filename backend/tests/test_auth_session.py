"""記住帳密 + 閒置自動登出 + session 失效。"""
from datetime import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.auth import hash_password
from backend.app.config import ALGORITHM, SECRET_KEY
from backend.app.database import Base, get_db
from backend.app.main import app
from backend.app.models import Employee, Store
from backend.app.services.idle_policy import IDLE_MS, WARN_BEFORE_MS, IdleTracker
from backend.app.services.remember_policy import (
    REMEMBER_FLAG_KEY,
    REMEMBER_USER_KEY,
    apply_remember_preference,
    assert_no_plaintext_password,
    load_remembered_username,
)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(bind=engine)
Base.metadata.create_all(bind=engine)


def override_get_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

ROOT = Path(__file__).resolve().parents[2]
AUTH_JS = (ROOT / "frontend" / "static" / "js" / "auth_session.js").read_text(encoding="utf-8")
INDEX_HTML = (ROOT / "frontend" / "index.html").read_text(encoding="utf-8")
APP_JS = (ROOT / "frontend" / "static" / "js" / "app.js").read_text(encoding="utf-8")


@pytest.fixture(autouse=True)
def clean_db():
    app.dependency_overrides[get_db] = override_get_db
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSession()
    s1 = Store(name="店舖1", code="store1", gps_radius_m=100)
    db.add(s1)
    db.flush()
    admin = Employee(
        name="管理員",
        schedule_code="ADMIN",
        store_id=s1.id,
        username="admin",
        password_hash=hash_password("admin123"),
        role="admin",
        is_active=True,
        agreed_daily_hours=8,
        break_start=time(12, 0),
        break_end=time(13, 0),
    )
    emp = Employee(
        name="測試員工",
        schedule_code="傑",
        store_id=s1.id,
        username="emp1",
        password_hash=hash_password("emp123"),
        role="employee",
        is_active=True,
        agreed_daily_hours=8,
        break_start=time(12, 0),
        break_end=time(13, 0),
    )
    db.add_all([admin, emp])
    db.commit()
    db.close()
    yield


def test_remember_unchecked_does_not_save():
    storage = {}
    apply_remember_preference(storage, username="emp1", password="emp123", remember=False)
    assert REMEMBER_FLAG_KEY not in storage
    assert REMEMBER_USER_KEY not in storage
    assert load_remembered_username(storage) is None
    assert assert_no_plaintext_password(storage)


def test_remember_checked_saves_username_for_next_login():
    storage = {}
    apply_remember_preference(storage, username="emp1", password="emp123", remember=True)
    assert storage.get(REMEMBER_FLAG_KEY) == "1"
    assert load_remembered_username(storage) == "emp1"


def test_remember_never_stores_plaintext_password():
    storage = {}
    apply_remember_preference(storage, username="emp1", password="secret-plain", remember=True)
    assert assert_no_plaintext_password(storage)
    assert "secret-plain" not in "".join(str(v) for v in storage.values())
    for bad in ("attendance_password", "attendance_remember_password"):
        assert bad not in AUTH_JS
    assert "PasswordCredential" in AUTH_JS
    assert "credentials.store" in AUTH_JS
    assert "記住帳密" in INDEX_HTML
    assert "remember-credentials" in INDEX_HTML


def test_activity_resets_idle_timer():
    t = IdleTracker()
    t.activity(0)
    assert not t.should_logout(IDLE_MS - 1)
    t.activity(120_000)
    assert not t.should_logout(120_000 + IDLE_MS - 1)
    assert t.should_logout(120_000 + IDLE_MS)


def test_mouse_events_listed_as_activity():
    for ev in ("mousedown", "mousemove", "mouseup", "click", "pointermove", "pointerdown"):
        assert ev in AUTH_JS


def test_keyboard_events_listed_as_activity():
    for ev in ("keydown", "keyup", "keypress", "input"):
        assert ev in AUTH_JS


def test_touch_events_listed_as_activity():
    for ev in ("touchstart", "touchmove", "touchend"):
        assert ev in AUTH_JS


def test_scroll_events_listed_as_activity():
    for ev in ("scroll", "wheel"):
        assert ev in AUTH_JS


def test_idle_three_minutes_triggers_logout():
    t = IdleTracker()
    t.activity(0)
    assert not t.should_logout(IDLE_MS - 1)
    assert t.should_logout(IDLE_MS)
    assert IDLE_MS == 3 * 60 * 1000


def test_logout_invalidates_backend_session():
    r = client.post("/api/auth/login", json={"username": "emp1", "password": "emp123"})
    assert r.status_code == 200
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200

    out = client.post("/api/auth/logout", headers=h)
    assert out.status_code == 200

    me = client.get("/api/auth/me", headers=h)
    assert me.status_code == 401

    punch = client.get("/api/punch/today", headers=h)
    assert punch.status_code == 401


def test_after_logout_cannot_reuse_token_like_browser_back():
    r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    client.post("/api/auth/logout", headers=h)
    assert client.get("/api/dashboard", headers=h).status_code == 401
    assert client.get("/api/auth/me", headers=h).status_code == 401
    assert "protectHistory" in AUTH_JS
    assert "popstate" in AUTH_JS
    assert "pageshow" in AUTH_JS


def test_idle_warn_at_thirty_seconds_before():
    t = IdleTracker()
    t.activity(0)
    warn_at = IDLE_MS - WARN_BEFORE_MS
    assert not t.should_warn(warn_at - 1)
    assert t.should_warn(warn_at)
    t.mark_warn_shown()
    assert not t.should_warn(warn_at + 1000)
    assert WARN_BEFORE_MS == 30_000
    assert "30秒後將自動登出" in INDEX_HTML
    assert "idle-continue" in INDEX_HTML


def test_continue_use_cancels_logout():
    t = IdleTracker()
    t.activity(0)
    t.should_warn(IDLE_MS - WARN_BEFORE_MS)
    t.mark_warn_shown()
    t.continue_use(IDLE_MS - 10_000)
    assert not t.should_logout(IDLE_MS - 10_000 + IDLE_MS - 1)
    assert t.should_logout(IDLE_MS - 10_000 + IDLE_MS)
    assert "continueUse" in AUTH_JS
    assert "繼續使用" in INDEX_HTML


def test_makeup_input_counts_as_activity():
    assert "input" in AUTH_JS
    assert "makeup" in APP_JS
    t = IdleTracker()
    t.activity(0)
    t.activity(170_000)
    assert not t.should_logout(170_000 + IDLE_MS - 1)


def test_token_has_jti_for_revocation():
    r = client.post("/api/auth/login", json={"username": "emp1", "password": "emp123"})
    token = r.json()["access_token"]
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload.get("jti")


def test_server_idle_timeout_returns_401():
    from datetime import timedelta

    from backend.app.config import IDLE_TIMEOUT_MINUTES
    from backend.app.models import TokenActivity
    from backend.app.timeutil import now_naive_local

    r = client.post("/api/auth/login", json={"username": "emp1", "password": "emp123"})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.get("/api/auth/me", headers=h).status_code == 200

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    jti = payload["jti"]
    db = TestingSession()
    try:
        row = db.query(TokenActivity).filter(TokenActivity.jti == jti).first()
        assert row is not None
        row.last_activity_at = now_naive_local() - timedelta(minutes=IDLE_TIMEOUT_MINUTES + 1)
        db.commit()
    finally:
        db.close()

    me = client.get("/api/auth/me", headers=h)
    assert me.status_code == 401
    assert "閒置" in (me.json().get("detail") or "")


def test_activity_heartbeat_endpoint():
    r = client.post("/api/auth/login", json={"username": "emp1", "password": "emp123"})
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/auth/activity", headers=h).status_code == 200
    assert "pingServerActivity" in AUTH_JS
    assert "/api/auth/activity" in AUTH_JS


def test_admin_and_employee_both_use_idle_logout_ui():
    admin_html = (ROOT / "frontend" / "admin.html").read_text(encoding="utf-8")
    assert "auth_session.js" in INDEX_HTML
    assert "auth_session.js" in admin_html
    assert "idle-modal" in admin_html
