from __future__ import annotations

from pydantic import BaseModel


class OverviewStats(BaseModel):
    total_trades: int
    win_rate: float
    total_profit_loss: float
    average_profit_loss: float
    profit_loss_ratio: float | None
    profit_factor: float | None


class AssetBreakdown(BaseModel):
    asset_code: str
    asset_type: str
    trade_count: int
    win_rate: float
    total_profit_loss: float
