from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class ImportStatus(str, PyEnum):
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    broker: Mapped[str] = mapped_column(String(50))
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[ImportStatus] = mapped_column(Enum(ImportStatus, name="import_status"), default=ImportStatus.PENDING)
    error_message: Mapped[str | None] = mapped_column(String)
    total_records: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone: Mapped[str | None] = mapped_column(String(50))

    fills: Mapped[list["TradeFill"]] = relationship(back_populates="import_batch", cascade="all, delete-orphan")
