from __future__ import annotations

from datetime import datetime
from typing import Sequence

from pydantic import BaseModel, ConfigDict

from app.models.enums import AssetType, FillSide, TradeDirection


class TradeFillBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    side: FillSide
    direction: TradeDirection
    quantity: float
    price: float
    commission: float
    currency: str
    original_currency: str
    trade_time: datetime
    source: str | None = None
    order_id: str | None = None

class ParentTradeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    asset_id: int
    asset_code: str
    asset_type: AssetType
    direction: TradeDirection
    quantity: float
    open_time: datetime
    close_time: datetime | None
    open_price: float | None
    close_price: float | None
    total_commission: float
    profit_loss: float | None  # None for open positions
    currency: str
    original_currency: str

class ParentTradeWithFills(ParentTradeBase):
    fills: Sequence[TradeFillBase]
