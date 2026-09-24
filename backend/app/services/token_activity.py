"""JWT 活動／server-side idle timeout（節流寫入，避免每請求狂寫 DB）。"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from jose import JWTError, jwt
from sqlalchemy.orm import Session

from ..config import ALGORITHM, IDLE_TIMEOUT_MINUTES, SECRET_KEY
from ..models import TokenActivity
from ..timeutil import now_naive_local

# 距上次寫入超過此秒數才更新 last_activity（降低寫入量）
_WRITE_THROTTLE_SECONDS = 20


def _decode_jti_exp(token: str) -> tuple[Optional[str], Optional[datetime], Optional[int]]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None, None, None
    jti = payload.get("jti")
    exp = payload.get("exp")
    uid = payload.get("uid")
    expires_at = datetime.utcfromtimestamp(exp) if exp else now_naive_local() + timedelta(days=7)
    return jti, expires_at, uid if isinstance(uid, int) else None


def touch_token_activity(
    db: Session,
    token: str,
    *,
    force: bool = False,
    employee_id: Optional[int] = None,
) -> None:
    """登入或活動時更新 last_activity（預設節流）。"""
    jti, expires_at, uid = _decode_jti_exp(token)
    if not jti or not expires_at:
        return
    now = now_naive_local()
    row = db.query(TokenActivity).filter(TokenActivity.jti == jti).first()
    emp = employee_id if employee_id is not None else uid
    if row is None:
        db.add(
            TokenActivity(
                jti=jti,
                employee_id=emp,
                last_activity_at=now,
                expires_at=expires_at,
            )
        )
        db.commit()
        return
    elapsed = (now - row.last_activity_at).total_seconds()
    if force or elapsed >= _WRITE_THROTTLE_SECONDS:
        row.last_activity_at = now
        row.expires_at = expires_at
        if emp is not None:
            row.employee_id = emp
        db.commit()


def assert_token_not_idle(db: Session, token: str) -> None:
    """
    若超過 IDLE_TIMEOUT_MINUTES 無活動 → 視為失效。
    無 activity 列時：以 JWT iat 近似（相容舊 token），並建立 activity。
    """
    from fastapi import HTTPException

    jti, expires_at, uid = _decode_jti_exp(token)
    if not jti:
        return
    now = now_naive_local()
    idle_delta = timedelta(minutes=IDLE_TIMEOUT_MINUTES)
    row = db.query(TokenActivity).filter(TokenActivity.jti == jti).first()
    if row is None:
        # 舊 token：建立 activity 起點為 now（不立即踢出），之後才計 idle
        touch_token_activity(db, token, force=True, employee_id=uid)
        return
    if now - row.last_activity_at > idle_delta:
        from ..models import RevokedToken

        if not db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
            db.add(RevokedToken(jti=jti, expires_at=expires_at or now))
            db.commit()
        db.query(TokenActivity).filter(TokenActivity.jti == jti).delete()
        db.commit()
        raise HTTPException(status_code=401, detail="閒置逾時，請重新登入")
    # 通過檢查時輕量節流更新
    touch_token_activity(db, token, force=False, employee_id=uid)


def clear_token_activity(db: Session, token: str) -> None:
    jti, _, _ = _decode_jti_exp(token)
    if not jti:
        return
    db.query(TokenActivity).filter(TokenActivity.jti == jti).delete()
    db.commit()
