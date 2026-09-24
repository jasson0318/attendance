from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, SECRET_KEY
from .database import get_db
from .models import Employee, RevokedToken
from .services.token_activity import assert_token_not_idle, clear_token_activity, touch_token_activity

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "jti": uuid4().hex})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _is_revoked(db: Session, jti: Optional[str]) -> bool:
    if not jti:
        return False
    row = db.query(RevokedToken).filter(RevokedToken.jti == jti).first()
    return row is not None


def revoke_token(db: Session, token: str) -> None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return
    jti = payload.get("jti")
    if not jti:
        return
    if db.query(RevokedToken).filter(RevokedToken.jti == jti).first():
        return
    exp = payload.get("exp")
    expires_at = datetime.utcfromtimestamp(exp) if exp else datetime.utcnow() + timedelta(days=7)
    db.add(RevokedToken(jti=jti, expires_at=expires_at))
    db.commit()
    clear_token_activity(db, token)


def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: Session = Depends(get_db),
) -> Employee:
    if not creds:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登入")
    token = creds.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        jti: str = payload.get("jti")
        if not username:
            raise HTTPException(status_code=401, detail="無效憑證")
        if _is_revoked(db, jti):
            raise HTTPException(status_code=401, detail="登入已失效，請重新登入")
        assert_token_not_idle(db, token)
    except JWTError:
        raise HTTPException(status_code=401, detail="無效憑證")
    user = db.query(Employee).filter(Employee.username == username).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="帳號不存在或已停用")
    return user


def require_admin(user: Employee = Depends(get_current_user)) -> Employee:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="需要管理員權限")
    return user


def register_login_activity(db: Session, token: str, employee_id: int) -> None:
    touch_token_activity(db, token, force=True, employee_id=employee_id)
