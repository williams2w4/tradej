from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.core.currency import convert_amount, normalize_currency
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


def _year_bounds(year: int, timezone: str) -> tuple[datetime, datetime]:
    tz = ZoneInfo(timezone)
    start_local = datetime(year, 1, 1, tzinfo=tz)
    end_local = datetime(year + 1, 1, 1, tzinfo=tz)
    return start_local.astimezone(ZoneInfo("UTC")), end_local.astimezone(ZoneInfo("UTC"))


@router.get("", response_model=list[CalendarDay])
async def calendar_view(
    year: int = Query(..., ge=1900, le=2100),
    month: int = Query(..., ge=1, le=12),
    asset_code: str | None = None,
    asset_type: AssetType | None = None,
    direction: TradeDirection | None = None,
    timezone: str = Query(default="UTC"),
    currency: str = Query(default="USD"),
    mode: str = Query(default="month"),
    db: AsyncSession = Depends(get_db),
) -> list[CalendarDay]:
    target_currency = normalize_currency(currency)

    if mode == "year":
        start_utc, end_utc = _year_bounds(year, timezone)
    else:
        start_utc, end_utc = _month_bounds(year, month, timezone)

    stmt = (
        select(ParentTrade)
        .join(Asset)
        .options(selectinload(ParentTrade.asset))
        .where(
            (ParentTrade.open_time >= start_utc)
            & (ParentTrade.open_time < end_utc)
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

    def default_bucket() -> dict[str, int | Decimal]:
        return {"count": 0, "wins": 0, "pnl": Decimal("0")}

    buckets: dict[date, dict[str, int | Decimal]] = defaultdict(default_bucket)

    for trade in trades:
        reference = trade.open_time
        local_dt = reference.astimezone(tz)
        if mode == "year":
            bucket_key = date(local_dt.year, local_dt.month, 1)
        else:
            bucket_key = local_dt.date()
        bucket = buckets[bucket_key]
        bucket["count"] = int(bucket["count"]) + 1
        pnl = convert_amount(trade.profit_loss, trade.currency, target_currency)
        if pnl > 0:
            bucket["wins"] = int(bucket["wins"]) + 1
        bucket["pnl"] = Decimal(bucket["pnl"]) + pnl

    return [
        CalendarDay(
            date=day,
            trade_count=int(data["count"]),
            total_profit_loss=float(data["pnl"]),
            win_rate=(int(data["wins"]) / int(data["count"])) if data["count"] else 0.0,
        )
        for day, data in sorted(buckets.items(), key=lambda item: item[0])
    ]
