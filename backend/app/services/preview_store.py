"""Excel 匯入預覽快取抽象：本機 Memory；Cloud 可用 Postgres。"""
from __future__ import annotations

import json
import os
import pickle
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Any, Optional

from sqlalchemy.orm import Session

from ..models import Base
from sqlalchemy import DateTime, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column


class ExcelPreviewBlob(Base):
    """PostgresPreviewStore 用的暫存表（SQLite／PG 皆可）。"""

    __tablename__ = "excel_preview_blobs"

    cache_key: Mapped[str] = mapped_column(String(200), primary_key=True)
    payload: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PreviewStore(ABC):
    @abstractmethod
    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None: ...

    @abstractmethod
    def get(self, key: str) -> Optional[Any]: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class MemoryPreviewStore(PreviewStore):
    """單行程記憶體（開發／單實例）。"""

    def __init__(self) -> None:
        self._data: dict[str, tuple[Any, datetime]] = {}

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        self._data[key] = (value, datetime.utcnow() + timedelta(seconds=ttl_seconds))

    def get(self, key: str) -> Optional[Any]:
        item = self._data.get(key)
        if not item:
            return None
        value, exp = item
        if datetime.utcnow() > exp:
            self._data.pop(key, None)
            return None
        return value

    def delete(self, key: str) -> None:
        self._data.pop(key, None)


class PostgresPreviewStore(PreviewStore):
    """可跨多 instance 的 DB 暫存（pickle；僅內部暫存非機密業務物件）。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def set(self, key: str, value: Any, ttl_seconds: int = 3600) -> None:
        blob = pickle.dumps(value, protocol=pickle.HIGHEST_PROTOCOL)
        exp = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        row = self.db.query(ExcelPreviewBlob).filter(ExcelPreviewBlob.cache_key == key).first()
        if row:
            row.payload = blob
            row.expires_at = exp
        else:
            self.db.add(ExcelPreviewBlob(cache_key=key, payload=blob, expires_at=exp))
        self.db.commit()

    def get(self, key: str) -> Optional[Any]:
        row = self.db.query(ExcelPreviewBlob).filter(ExcelPreviewBlob.cache_key == key).first()
        if not row:
            return None
        if datetime.utcnow() > row.expires_at:
            self.db.delete(row)
            self.db.commit()
            return None
        return pickle.loads(row.payload)

    def delete(self, key: str) -> None:
        self.db.query(ExcelPreviewBlob).filter(ExcelPreviewBlob.cache_key == key).delete()
        self.db.commit()


_memory_singleton = MemoryPreviewStore()


def get_preview_store(db: Session | None = None) -> PreviewStore:
    """
    PREVIEW_STORE=memory|postgres
    正式多實例建議 postgres；開發預設 memory。
    """
    mode = (os.environ.get("PREVIEW_STORE") or "memory").strip().lower()
    if mode in ("postgres", "db", "database"):
        if db is None:
            raise RuntimeError("PostgresPreviewStore 需要 db session")
        return PostgresPreviewStore(db)
    return _memory_singleton
