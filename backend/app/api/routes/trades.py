from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import and_, delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_db
from app.core.currency import normalize_currency
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


def _serialize_trade(trade: ParentTrade) -> ParentTradeWithFills:
    original_currency = normalize_currency(trade.currency)

    sorted_fills = sorted(trade.fills, key=lambda f: f.trade_time)
    serialized_fills = []
    for fill in sorted_fills:
        direction = (
            TradeDirection.LONG
            if fill.side == FillSide.BUY
            else TradeDirection.SHORT
        )
        serialized_fills.append(
            TradeFillBase(
                id=fill.id,
                side=fill.side,
                direction=direction,
                quantity=float(fill.quantity),
                price=float(fill.price),
                commission=float(fill.commission),
                currency=normalize_currency(fill.currency),
                original_currency=normalize_currency(fill.currency),
                trade_time=fill.trade_time,
                source=fill.source,
                order_id=fill.order_id,
            )
        )
    # For open positions (close_time is None), don't show profit_loss
    profit_loss_value = float(trade.profit_loss) if trade.close_time is not None else None
    
    return ParentTradeWithFills(
        id=trade.id,
        asset_id=trade.asset_id,
        asset_code=trade.asset.code,
        asset_type=trade.asset.asset_type,
        direction=trade.direction,
        quantity=float(trade.quantity),
        open_time=trade.open_time,
        close_time=trade.close_time,
        open_price=float(trade.open_price) if trade.open_price is not None else None,
        close_price=float(trade.close_price) if trade.close_price is not None else None,
        total_commission=float(trade.total_commission),
        profit_loss=profit_loss_value,
        currency=original_currency,
        original_currency=original_currency,
        fills=serialized_fills,
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
    return [_serialize_trade(trade) for trade in trades]


@router.delete("/{trade_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trade(trade_id: int, db: AsyncSession = Depends(get_db)) -> Response:
    trade = await db.get(ParentTrade, trade_id)
    if trade is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Trade not found")

    await db.delete(trade)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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

    target_timezone_name = timezone
    try:
        target_tz = ZoneInfo(timezone)
    except Exception:  # noqa: BLE001
        target_tz = ZoneInfo("UTC")
        target_timezone_name = "UTC"

    def _format_number(value: float) -> str:
        text = f"{value:.6f}"
        text = text.rstrip("0").rstrip(".")
        return text if text else "0"

    recent_fills = fills[-100:]

    lines = [
        "//@version=6",
        'indicator("交易记录可视化", "Trade Records", overlay=true, max_labels_count=500, max_lines_count=500)',
        "",
        'show_buy_labels = input.bool(true, "显示买入标记", group="显示选项")',
        'show_sell_labels = input.bool(true, "显示卖出标记", group="显示选项")',
        "",
        "var tradeData = array.new<string>()",
        "",
        "if barstate.isfirst",
        "    array.clear(tradeData)",
    ]

    if len(fills) > 100:
        lines.append(f"    // 仅展示最近100条交易，共{len(fills)}条记录")

    for fill in recent_fills:
        trade_time_local = fill.trade_time.astimezone(target_tz)
        time_str = trade_time_local.strftime("%Y-%m-%dT%H:%M:%S")
        direction = (
            TradeDirection.LONG
            if fill.side == FillSide.BUY
            else TradeDirection.SHORT
        )
        side = 1 if direction == TradeDirection.LONG else -1
        qty_text = _format_number(float(fill.quantity))
        price_text = _format_number(float(fill.price))
        comment = f"{fill.asset.code} {direction.value} {qty_text}@{price_text}"
        safe_comment = comment.replace("\\", "\\\\").replace("\"", "\\\"")
        entry = f"{time_str},{side},{qty_text},{price_text},{safe_comment}"
        safe_entry = entry.replace("\\", "\\\\").replace("\"", "\\\"")
        lines.append(f'    array.push(tradeData, "{safe_entry}")')

    lines.extend([
        "",
        "parse_trade_time(time_str) =>",
        "    year_str = str.substring(time_str, 0, 4)",
        "    month_str = str.substring(time_str, 5, 7)",
        "    day_str = str.substring(time_str, 8, 10)",
        "    hour_str = str.substring(time_str, 11, 13)",
        "    min_str = str.substring(time_str, 14, 16)",
        "    sec_str = str.substring(time_str, 17, 19)",
        "    year_int = math.round(str.tonumber(year_str))",
        "    month_int = math.round(str.tonumber(month_str))",
        "    day_int = math.round(str.tonumber(day_str))",
        "    hour_int = math.round(str.tonumber(hour_str))",
        "    min_int = math.round(str.tonumber(min_str))",
        "    sec_int = math.round(str.tonumber(sec_str))",
        "    // 使用上海时区 (UTC+8)",
        '    timestamp("GMT+8", year_int, month_int, day_int, hour_int, min_int, sec_int)',
        "",
        "// 简化版本：处理交易并合并同一K线同方向的交易",
        "if barstate.islast and array.size(tradeData) > 0",
        "    // 创建用于存储合并后交易的数组",
        "    merged_keys = array.new<string>()     // 存储\"bar_time_side\"格式的键",
        "    merged_qty = array.new<float>()       // 存储合并后的数量",
        "    merged_price = array.new<float>()     // 存储价格（第一笔交易的价格）",
        "    merged_comment = array.new<string>()  // 存储备注",
        "    merged_bar_time = array.new<int>()    // 存储K线时间",
        "    merged_high = array.new<float>()      // 存储K线最高价",
        "    merged_low = array.new<float>()       // 存储K线最低价",
        "    merged_side = array.new<float>()      // 存储交易方向",
        "    ",
        "    // 处理所有交易记录",
        "    for i = 0 to array.size(tradeData) - 1",
        "        trade_str = array.get(tradeData, i)",
        '        parts = str.split(trade_str, ",")',
        "        if array.size(parts) >= 5",
        "            time_str = array.get(parts, 0)",
        "            side_str = array.get(parts, 1)",
        "            qty_str = array.get(parts, 2)",
        "            price_str = array.get(parts, 3)",
        "            comment = array.get(parts, 4)",
        "            ",
        "            // 验证数据完整性",
        "            if str.length(time_str) > 0 and str.length(side_str) > 0 and str.length(qty_str) > 0 and str.length(price_str) > 0",
        "                trade_time = parse_trade_time(time_str)",
        "                side = str.tonumber(side_str)",
        "                qty = str.tonumber(qty_str)",
        "                price = str.tonumber(price_str)",
        "                ",
        "                // 验证转换后的数值有效性",
        "                if not na(trade_time) and not na(side) and not na(qty) and not na(price)",
        "                    // 寻找匹配的K线",
        "                    bar_duration_ms = timeframe.in_seconds() * 1000",
        "                    found_match = false",
        "                    matched_bar_index = 0",
        "                    ",
        "                    // 遍历历史K线寻找匹配",
        "                    for j = 0 to bar_index",
        "                        bar_time = time[j]",
        "                        bar_end_time = bar_time + bar_duration_ms",
        "                        ",
        "                        if trade_time >= bar_time and trade_time < bar_end_time",
        "                            found_match := true",
        "                            matched_bar_index := j",
        "                            break",
        "                    ",
        "                    // 如果没有精确匹配，寻找最近的K线",
        "                    if not found_match",
        "                        min_diff = math.abs(trade_time - time[bar_index])",
        "                        matched_bar_index := bar_index",
        "                        for j = 0 to bar_index",
        "                            diff = math.abs(trade_time - time[j])",
        "                            if diff < min_diff",
        "                                min_diff := diff",
        "                                matched_bar_index := j",
        "                        found_match := true",
        "                    ",
        "                    if found_match",
        "                        target_high = high[matched_bar_index]",
        "                        target_low = low[matched_bar_index]",
        "                        matched_bar_time = time[matched_bar_index]",
        "                        ",
        "                        // 创建唯一键：K线时间_交易方向",
        "                        merge_key = str.tostring(matched_bar_time) + \"_\" + str.tostring(side)",
        "                        ",
        "                        // 查找是否已存在相同的键",
        "                        existing_index = -1",
        "                        if array.size(merged_keys) > 0",
        "                            for k = 0 to array.size(merged_keys) - 1",
        "                                if array.get(merged_keys, k) == merge_key",
        "                                    existing_index := k",
        "                                    break",
        "                        ",
        "                        if existing_index >= 0",
        "                            // 已存在，累加数量",
        "                            current_qty = array.get(merged_qty, existing_index)",
        "                            array.set(merged_qty, existing_index, current_qty + qty)",
        "                        else",
        "                            // 不存在，添加新记录",
        "                            array.push(merged_keys, merge_key)",
        "                            array.push(merged_qty, qty)",
        "                            array.push(merged_price, price)",
        "                            array.push(merged_comment, comment)",
        "                            array.push(merged_bar_time, matched_bar_time)",
        "                            array.push(merged_high, target_high)",
        "                            array.push(merged_low, target_low)",
        "                            array.push(merged_side, side)",
        "    ",
        "    // 创建合并后的标签",
        "    if array.size(merged_keys) > 0",
        "        for i = 0 to array.size(merged_keys) - 1",
        "            side = array.get(merged_side, i)",
        "            qty = array.get(merged_qty, i)",
        "            price = array.get(merged_price, i)",
        "            comment = array.get(merged_comment, i)",
        "            matched_bar_time = array.get(merged_bar_time, i)",
        "            target_high = array.get(merged_high, i)",
        "            target_low = array.get(merged_low, i)",
        "            ",
        "            if side > 0 and show_buy_labels",
        '                buy_text = str.tostring(qty, "#") + "\\n" + str.tostring(price, "#.##")',
        "                offset = math.max((target_high - target_low) * 0.15, syminfo.mintick * 5)",
        "                label_y = target_low - offset",
        "                label.new(matched_bar_time, label_y, buy_text, xloc=xloc.bar_time, style=label.style_label_up, color=color.new(color.green, 20), textcolor=color.white, size=size.small, tooltip=comment)",
        "            else if side < 0 and show_sell_labels",
        '                sell_text = str.tostring(qty, "#") + "\\n" + str.tostring(price, "#.##")',
        "                offset = math.max((target_high - target_low) * 0.15, syminfo.mintick * 5)",
        "                label_y = target_high + offset",
        "                label.new(matched_bar_time, label_y, sell_text, xloc=xloc.bar_time, style=label.style_label_down, color=color.new(color.red, 20), textcolor=color.white, size=size.small, tooltip=comment)",
        "",
        "plot(na)",
    ])

    return "\n".join(lines)
