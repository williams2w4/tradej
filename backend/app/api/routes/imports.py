from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.models import ImportBatch
from app.schemas.imports import ImportBatchRead
from app.services.ibkr_importer import DuplicateTradeError, ImportValidationError, import_ibkr_csv

router = APIRouter(prefix="/api/imports", tags=["imports"])

logger = logging.getLogger(__name__)

@router.post("", response_model=ImportBatchRead, status_code=status.HTTP_201_CREATED)
async def create_import(
    broker: str = Form(...),
    file: UploadFile = File(...),
    override_duplicates: bool = Form(False),
    db: AsyncSession = Depends(get_db),
) -> ImportBatch:
    if broker.lower() != "ibkr":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported broker")
    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file uploaded")
    try:
        batch = await import_ibkr_csv(db, contents, file.filename, override_duplicates=override_duplicates)
        await db.commit()
    except DuplicateTradeError as exc:
        await db.rollback()
        logger.warning("Duplicate trades detected for file %s: %s", file.filename, exc)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "duplicates_only", "message": str(exc), "duplicates": exc.duplicate_count},
        ) from exc
    except ImportValidationError as exc:
        await db.rollback()
        logger.warning("Import validation failed for file %s: %s", file.filename, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("Unexpected error importing file %s", file.filename)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to import trades") from exc
    await db.refresh(batch)
    return batch


@router.get("", response_model=list[ImportBatchRead])
async def list_imports(db: AsyncSession = Depends(get_db)) -> list[ImportBatch]:
    result = await db.execute(select(ImportBatch).order_by(ImportBatch.created_at.desc()))
    return result.scalars().all()
