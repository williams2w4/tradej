from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.core.currency import convert_amount, normalize_currency
from app.models import Asset, AssetType, ParentTrade, TradeFill
from app.models.trade import FillSide, TradeDirection
from app.schemas.trade import ParentTradeWithFills, TradeFillBase

router = APIRouter(prefix="/api/trades", tags=["trades"])


def _parse_datetime(dt: datetime | None, timezone: str) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        tz = ZoneInfo(timezone)
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(ZoneInfo("UTC"))


def _serialize_trade(trade: ParentTrade, target_currency: str | None = None) -> ParentTradeWithFills:
    original_currency = normalize_currency(trade.currency)
    display_currency = normalize_currency(target_currency) if target_currency else original_currency

    def convert_trade_value(value: float | None) -> float | None:
        if value is None:
            return None
        return float(convert_amount(value, original_currency, display_currency))

    fills = [
        TradeFillBase(
            id=fill.id,
            side=fill.side,
            quantity=float(fill.quantity),
            price=float(convert_amount(fill.price, fill.currency, display_currency)),
            commission=float(convert_amount(fill.commission, fill.currency, display_currency)),
            currency=display_currency,
            original_currency=normalize_currency(fill.currency),
            trade_time=fill.trade_time,
            source=fill.source,
            order_id=fill.order_id,
        )
        for fill in sorted(trade.fills, key=lambda f: f.trade_time)
    ]
    return ParentTradeWithFills(
        id=trade.id,
        asset_id=trade.asset_id,
        asset_code=trade.asset.code,
        asset_type=trade.asset.asset_type,
        direction=trade.direction,
        quantity=float(trade.quantity),
        open_time=trade.open_time,
        close_time=trade.close_time,
        open_price=convert_trade_value(float(trade.open_price)) if trade.open_price is not None else None,
        close_price=convert_trade_value(float(trade.close_price)) if trade.close_price is not None else None,
        total_commission=float(convert_amount(trade.total_commission, original_currency, display_currency)),
        profit_loss=float(convert_amount(trade.profit_loss, original_currency, display_currency)),
        currency=display_currency,
        original_currency=original_currency,
        fills=fills,
    )


@router.get("", response_model=list[ParentTradeWithFills])
async def list_trades(
    asset_code: str | None = None,
    asset_type: AssetType | None = None,
    direction: TradeDirection | None = None,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    timezone: str = Query(default="UTC"),
    db: AsyncSession = Depends(get_db),
    currency: str | None = Query(default=None),
) -> list[ParentTradeWithFills]:
    start_utc = _parse_datetime(start, timezone)
    end_utc = _parse_datetime(end, timezone)

    stmt = (
        select(ParentTrade)
        .join(Asset)
        .options(selectinload(ParentTrade.asset), selectinload(ParentTrade.fills))
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

    result = await db.execute(stmt)
    trades = result.scalars().unique().all()
    target_currency = normalize_currency(currency) if currency else None
    return [_serialize_trade(trade, target_currency) for trade in trades]


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_all_trades(db: AsyncSession = Depends(get_db)) -> Response:
    await db.execute(delete(TradeFill))
    await db.execute(delete(ParentTrade))
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/fills/export", response_class=PlainTextResponse)
async def export_fills(
    asset_code: str | None = None,
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    timezone: str = Query(default="UTC"),
    db: AsyncSession = Depends(get_db),
) -> str:
    start_utc = _parse_datetime(start, timezone)
    end_utc = _parse_datetime(end, timezone)

    stmt = select(TradeFill).join(Asset).options(selectinload(TradeFill.asset)).order_by(TradeFill.trade_time)
    if asset_code:
        stmt = stmt.where(Asset.code == asset_code)
    if start_utc:
        stmt = stmt.where(TradeFill.trade_time >= start_utc)
    if end_utc:
        stmt = stmt.where(TradeFill.trade_time <= end_utc)

    result = await db.execute(stmt)
    fills = result.scalars().all()
    if not fills:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No fills to export")

    lines = ["//@version=5", "indicator(\"Trade Journal Fills\", overlay=true)"]
    lines.append("var int[] tradeTimes = array.new_int()")
    lines.append("var string[] tradeTexts = array.new_string()")
    lines.append("if barstate.isfirst")
    for fill in fills:
        timestamp = int(fill.trade_time.timestamp() * 1000)
        side_text = "BUY" if fill.side == FillSide.BUY else "SELL"
        text = f"{fill.asset.code} {side_text} {float(fill.quantity)}@{float(fill.price)}"
        safe_text = text.replace("\"", "\\\"")
        lines.append(f"    array.push(tradeTimes, {timestamp})")
        lines.append(f"    array.push(tradeTexts, \"{safe_text}\")")
    lines.append("for i = 0 to array.size(tradeTimes) - 1")
    lines.append("    if time == array.get(tradeTimes, i)")
    lines.append(
        "        label.new(bar_index, close, array.get(tradeTexts, i), style=label.style_label_down, color=color.new(color.blue, 0))"
    )

    return "\n".join(lines)
