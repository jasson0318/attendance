import json
from datetime import date

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Employee
from ..services.excel_export import export_annual, export_daily, export_monthly
from ..services.excel_import import commit_import, parse_excel, preview_to_dict
from ..services.preview_store import get_preview_store

router = APIRouter(prefix="/api/excel", tags=["excel"])


@router.post("/import/preview")
async def excel_preview(
    store_id: int = Form(...),
    year: int = Form(...),
    month: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    content = await file.read()
    preview = parse_excel(content, store_id, db, year, month)
    key = f"{admin.id}:{store_id}:{year}:{month}"
    store = get_preview_store(db)
    store.set(key, preview, ttl_seconds=3600)
    return preview_to_dict(preview)


@router.post("/import/confirm")
def excel_confirm(
    store_id: int = Form(...),
    year: int = Form(...),
    month: int = Form(...),
    db: Session = Depends(get_db),
    admin: Employee = Depends(require_admin),
):
    key = f"{admin.id}:{store_id}:{year}:{month}"
    store = get_preview_store(db)
    preview = store.get(key)
    if not preview:
        raise HTTPException(400, "請先預覽再確認匯入")
    count = commit_import(db, preview, replace_month=True)
    store.delete(key)
    return {"message": f"已匯入 {count} 筆排班", "count": count}


@router.get("/export/daily")
def excel_daily(
    work_date: date,
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    data = export_daily(db, work_date, store_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="daily_{work_date}.xlsx"'},
    )


@router.get("/export/monthly")
def excel_monthly(
    year: int,
    month: int,
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    data = export_monthly(db, year, month, store_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="monthly_{year}_{month:02d}.xlsx"'},
    )


@router.get("/export/annual")
def excel_annual(
    year: int,
    store_id: int | None = None,
    db: Session = Depends(get_db),
    _: Employee = Depends(require_admin),
):
    data = export_annual(db, year, store_id)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="annual_{year}.xlsx"'},
    )
