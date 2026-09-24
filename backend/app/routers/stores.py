from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Employee, Store
from ..schemas import StoreOut, StoreUpdate

router = APIRouter(prefix="/api/stores", tags=["stores"])


@router.get("", response_model=list[StoreOut])
def list_stores(
    db: Session = Depends(get_db),
    user: Employee = Depends(require_admin),
):
    return db.query(Store).order_by(Store.id).all()


@router.get("/{store_id}", response_model=StoreOut)
def get_store(
    store_id: int,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    s = db.query(Store).filter(Store.id == store_id).first()
    if not s:
        raise HTTPException(404, "找不到店舖")
    return s


@router.put("/{store_id}", response_model=StoreOut)
def update_store(
    store_id: int,
    body: StoreUpdate,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    s = db.query(Store).filter(Store.id == store_id).first()
    if not s:
        raise HTTPException(404, "找不到店舖")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(s, k, v)
    db.commit()
    db.refresh(s)
    return s
