from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.models import Asset, AssetType, ParentTrade
from app.models.trade import TradeDirection
from app.schemas.calendar import CalendarDay

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


def _month_bounds(year: int, month: int, timezone: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone)
    try:
        start_local = datetime(year, month, 1, tzinfo=tz)
    except ValueError as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="Invalid year or month") from exc
    if month == 12:
        end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    else:
        end_local = datetime(year, month + 1, 1, tzinfo=tz)
    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))


@router.get("", response_model=list[CalendarDay])
async def calendar_view(
    year: int = Query(..., ge=1900, le=2100),
    month: int = Query(..., ge=1, le=12),
    asset_code: str | None = None,
    asset_type: AssetType | None = None,
    direction: TradeDirection | None = None,
    timezone: str = Query(default="UTC"),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarDay]:
    start_utc, end_utc = _month_bounds(year, month, timezone)

    stmt = (
        select(ParentTrade)
        .join(Asset)
        .options(selectinload(ParentTrade.asset))
        .where(
            (
                (ParentTrade.close_time >= start_utc)
                & (ParentTrade.close_time < end_utc)
                & ParentTrade.close_time.is_not(None)
            )
            | (
                ParentTrade.close_time.is_(None)
                & (ParentTrade.open_time >= start_utc)
                & (ParentTrade.open_time < end_utc)
            )
        )
    )
    conditions = []
    if asset_code:
        conditions.append(Asset.code == asset_code)
    if asset_type:
        conditions.append(Asset.asset_type == asset_type)
    if direction:
        conditions.append(ParentTrade.direction == direction)
    if conditions:
        stmt = stmt.where(and_(*conditions))

    result = await db.execute(stmt)
    trades = result.scalars().all()

    tz = ZoneInfo(timezone)
    buckets: dict[date, dict[str, float | int]] = defaultdict(lambda: {"count": 0, "pnl": 0.0})

    for trade in trades:
        reference = trade.close_time or trade.open_time
        local_dt = reference.astimezone(tz)
        day = local_dt.date()
        bucket = buckets[day]
        bucket["count"] = int(bucket["count"]) + 1
        bucket["pnl"] = float(bucket["pnl"]) + float(trade.profit_loss)

    return [
        CalendarDay(date=day, trade_count=int(data["count"]), total_profit_loss=float(data["pnl"]))
        for day, data in sorted(buckets.items(), key=lambda item: item[0])
    ]
