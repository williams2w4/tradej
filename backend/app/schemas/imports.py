from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.import_batch import ImportStatus


class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    broker: str
    filename: str
    status: ImportStatus
    error_message: str | None
    total_records: int
    created_at: datetime
    completed_at: datetime | None
    timezone: str | None

