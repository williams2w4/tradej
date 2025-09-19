from __future__ import annotations

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class AssetType(str, PyEnum):
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(200))
    asset_type: Mapped[AssetType] = mapped_column(Enum(AssetType, name="asset_type"))
    exchange: Mapped[str | None] = mapped_column(String(50))
    timezone: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    trades: Mapped[list["ParentTrade"]] = relationship(back_populates="asset")
    fills: Mapped[list["TradeFill"]] = relationship(back_populates="asset")
