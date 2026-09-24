from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..auth import (
    create_access_token,
    get_current_user,
    register_login_activity,
    revoke_token,
    verify_password,
)
from ..database import get_db
from ..models import Employee
from ..schemas import LoginRequest, TokenResponse
from ..services.token_activity import touch_token_activity

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer(auto_error=False)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(Employee).filter(Employee.username == body.username).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="帳號或密碼錯誤")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="帳號已停用")
    token = create_access_token({"sub": user.username, "role": user.role, "uid": user.id})
    register_login_activity(db, token, user.id)
    return TokenResponse(
        access_token=token,
        role=user.role,
        name=user.name,
        employee_id=user.id,
    )


@router.post("/logout")
def logout(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
):
    """使目前 token 立即失效（前端閒置登出／手動登出都呼叫）。"""
    if creds and creds.credentials:
        revoke_token(db, creds.credentials)
    return {"message": "已登出"}


@router.post("/activity")
def activity(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
    user: Employee = Depends(get_current_user),
):
    """
    前端活動心跳（節流呼叫即可）。
    用於延長 server-side idle；真正 idle 判定在 get_current_user。
    """
    if creds and creds.credentials:
        touch_token_activity(db, creds.credentials, force=False, employee_id=user.id)
    return {"ok": True}


@router.get("/me")
def me(user: Employee = Depends(get_current_user)):
    return {
        "id": user.id,
        "name": user.name,
        "username": user.username,
        "role": user.role,
        "store_id": user.store_id,
        "schedule_code": user.schedule_code,
    }
