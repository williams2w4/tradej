from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models import Asset, AssetType, ParentTrade
from app.models.trade import TradeDirection
from app.schemas.stats import AssetBreakdown, OverviewStats

router = APIRouter(prefix="/api/stats", tags=["stats"])


def _parse_datetime(dt: datetime | None, timezone: str) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        tz = ZoneInfo(timezone)
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(ZoneInfo("UTC"))


def _load_trades(
    asset_code: str | None,
    asset_type: AssetType | None,
    direction: TradeDirection | None,
    start_utc: datetime | None,
    end_utc: datetime | None,
):
    stmt = (
        select(ParentTrade)
        .join(Asset)
        .options(selectinload(ParentTrade.asset))
        .order_by(ParentTrade.open_time.desc())
    )
    conditions = []
    if asset_code:
        conditions.append(Asset.code == asset_code)
    if asset_type:
        conditions.append(Asset.asset_type == asset_type)
    if direction:
        conditions.append(ParentTrade.direction == direction)
    if start_utc:
        conditions.append(ParentTrade.open_time >= start_utc)
    if end_utc:
        conditions.append(ParentTrade.open_time <= end_utc)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    return stmt


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    asset_code: str | None = None,
    asset_type: AssetType | None = None,
    direction: TradeDirection | None = None,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    timezone: str = Query(default="UTC"),
    db: AsyncSession = Depends(get_db),
) -> OverviewStats:
    start_utc = _parse_datetime(start, timezone)
    end_utc = _parse_datetime(end, timezone)
    stmt = _load_trades(asset_code, asset_type, direction, start_utc, end_utc)
    result = await db.execute(stmt)
    trades = result.scalars().all()

    total = len(trades)
    if total == 0:
        return OverviewStats(
            total_trades=0,
            win_rate=0.0,
            total_profit_loss=0.0,
            average_profit_loss=0.0,
            profit_loss_ratio=None,
            profit_factor=None,
        )

    total_pnl = sum(float(trade.profit_loss) for trade in trades)
    wins = [float(trade.profit_loss) for trade in trades if float(trade.profit_loss) > 0]
    losses = [float(trade.profit_loss) for trade in trades if float(trade.profit_loss) < 0]

    win_rate = len(wins) / total if total else 0.0
    average = total_pnl / total
    avg_win = (sum(wins) / len(wins)) if wins else None
    avg_loss = (sum(losses) / len(losses)) if losses else None
    profit_loss_ratio = (
        avg_win / abs(avg_loss)
        if avg_win is not None and avg_loss is not None and avg_loss != 0
        else None
    )
    profit_factor = (
        sum(wins) / abs(sum(losses))
        if wins and losses and sum(losses) != 0
        else None
    )

    return OverviewStats(
        total_trades=total,
        win_rate=win_rate,
        total_profit_loss=total_pnl,
        average_profit_loss=average,
        profit_loss_ratio=profit_loss_ratio,
        profit_factor=profit_factor,
    )


@router.get("/by-asset", response_model=list[AssetBreakdown])
async def stats_by_asset(
    asset_code: str | None = None,
    asset_type: AssetType | None = None,
    direction: TradeDirection | None = None,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    timezone: str = Query(default="UTC"),
    db: AsyncSession = Depends(get_db),
) -> list[AssetBreakdown]:
    start_utc = _parse_datetime(start, timezone)
    end_utc = _parse_datetime(end, timezone)
    stmt = _load_trades(asset_code, asset_type, direction, start_utc, end_utc)
    result = await db.execute(stmt)
    trades = result.scalars().all()

    summary: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {
            "asset_type": "",
            "trade_count": 0,
            "wins": 0,
            "total_pnl": 0.0,
        }
    )

    for trade in trades:
        key = trade.asset.code
        entry = summary[key]
        entry["asset_type"] = trade.asset.asset_type.value
        entry["trade_count"] = int(entry["trade_count"]) + 1
        pnl = float(trade.profit_loss)
        if pnl > 0:
            entry["wins"] = int(entry["wins"]) + 1
        entry["total_pnl"] = float(entry["total_pnl"]) + pnl

    breakdown = [
        AssetBreakdown(
            asset_code=code,
            asset_type=str(data["asset_type"]),
            trade_count=int(data["trade_count"]),
            win_rate=(int(data["wins"]) / int(data["trade_count"])) if data["trade_count"] else 0.0,
            total_profit_loss=float(data["total_pnl"]),
        )
        for code, data in summary.items()
    ]

    breakdown.sort(key=lambda item: item.trade_count, reverse=True)
    return breakdown
