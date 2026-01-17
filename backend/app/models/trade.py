from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.asset import Asset
from app.models.import_batch import ImportBatch
from app.models.enums import AssetType, FillSide, TradeDirection


class ParentTrade(Base):
    __tablename__ = "parent_trades"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    direction: Mapped[TradeDirection] = mapped_column(Enum(TradeDirection, name="trade_direction"))
    quantity: Mapped[float] = mapped_column(Numeric(18, 4))
    open_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    close_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    open_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    close_price: Mapped[float | None] = mapped_column(Numeric(18, 6))
    total_commission: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    profit_loss: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    currency: Mapped[str] = mapped_column(String(10))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    asset: Mapped[Asset] = relationship(back_populates="trades")
    fills: Mapped[list["TradeFill"]] = relationship(back_populates="parent_trade", cascade="all, delete-orphan")


class TradeFill(Base):
    __tablename__ = "trade_fills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    parent_trade_id: Mapped[int | None] = mapped_column(ForeignKey("parent_trades.id"), nullable=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    side: Mapped[FillSide] = mapped_column(Enum(FillSide, name="fill_side"))
    quantity: Mapped[float] = mapped_column(Numeric(18, 4))
    price: Mapped[float] = mapped_column(Numeric(18, 6))
    commission: Mapped[float] = mapped_column(Numeric(18, 6), default=0)
    currency: Mapped[str] = mapped_column(String(10))
    trade_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    source: Mapped[str | None] = mapped_column(String(50))
    order_id: Mapped[str | None] = mapped_column(String(100))
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    net_cash: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    parent_trade: Mapped[ParentTrade | None] = relationship(back_populates="fills")
    asset: Mapped[Asset] = relationship(back_populates="fills")
    import_batch: Mapped[ImportBatch] = relationship(back_populates="fills")
