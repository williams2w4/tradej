from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Asset,
    AssetType,
    ImportBatch,
    ImportStatus,
    ParentTrade,
    TradeFill,
)
from app.models.trade import FillSide
from app.services.aggregation import NormalizedFill, aggregate_parent_trades


@dataclass
class _CombinedFill:
    normalized: NormalizedFill
    kind: Literal["existing", "new"]
    existing_fill: TradeFill | None = None

EXCHANGE_TIMEZONES = {
    "ARCA": "America/New_York",
    "NYSE": "America/New_York",
    "NASDAQ": "America/New_York",
    "CBOE": "America/Chicago",
    "CME": "America/Chicago",
    "SMART": "America/New_York",
}

ASSET_TYPE_MAP = {
    "STK": AssetType.STOCK,
    "OPT": AssetType.OPTION,
    "FUT": AssetType.FUTURE,
}

REQUIRED_COLUMNS = {
    "Date/Time",
    "Symbol",
    "Buy/Sell",
    "Quantity",
    "Price",
    "Commission",
    "CurrencyPrimary",
}


class ImportValidationError(Exception):
    def __init__(self, message: str, row_number: int | None = None) -> None:
        if row_number is not None:
            super().__init__(f"Row {row_number}: {message}")
        else:
            super().__init__(message)


def _parse_ibkr_datetime(value: str, timezone: str) -> datetime:
    try:
        date_part, time_part = value.split(";")
        dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
    except Exception as exc:  # noqa: BLE001
        raise ImportValidationError(f"Invalid Date/Time value: {value}") from exc
    tz = ZoneInfo(timezone)
    return dt.replace(tzinfo=tz).astimezone(ZoneInfo("UTC"))


def _normalize_row(row: dict[str, str], row_number: int) -> NormalizedFill:
    missing = [col for col in REQUIRED_COLUMNS if not row.get(col)]
    if missing:
        raise ImportValidationError(f"Missing required columns: {', '.join(missing)}", row_number)

    symbol = row["Symbol"].strip()
    asset_class = row.get("AssetClass", "STK").strip()
    asset_type = ASSET_TYPE_MAP.get(asset_class, AssetType.STOCK)
    side_str = row["Buy/Sell"].strip().upper()
    if side_str not in ("BUY", "SELL"):
        raise ImportValidationError("Buy/Sell must be BUY or SELL", row_number)
    side = FillSide(side_str)

    try:
        quantity = abs(float(row["Quantity"]))
    except ValueError as exc:
        raise ImportValidationError("Quantity must be a number", row_number) from exc
    if quantity <= 0:
        raise ImportValidationError("Quantity must be greater than 0", row_number)

    try:
        price = float(row["Price"])
    except ValueError as exc:
        raise ImportValidationError("Price must be a number", row_number) from exc
    if price <= 0:
        raise ImportValidationError("Price must be greater than 0", row_number)

    try:
        commission_raw = float(row["Commission"])
    except ValueError as exc:
        raise ImportValidationError("Commission must be a number", row_number) from exc
    commission = abs(commission_raw)
    if commission < 0:
        raise ImportValidationError("Commission cannot be negative", row_number)

    currency = row["CurrencyPrimary"].strip()
    if not currency:
        raise ImportValidationError("Currency is required", row_number)

    exchange_field = row.get("ListingExchange", "")
    exchange = exchange_field.split(",")[0].split(";")[0].strip().upper() or None
    timezone = EXCHANGE_TIMEZONES.get(exchange, "America/New_York")
    trade_time = _parse_ibkr_datetime(row["Date/Time"], timezone)

    return NormalizedFill(
        asset_code=symbol,
        asset_type=asset_type,
        exchange=exchange,
        timezone=timezone,
        trade_time=trade_time,
        side=side,
        quantity=quantity,
        price=price,
        commission=commission,
        currency=currency,
        order_id=row.get("OrderID", "").strip() or None,
        source=row.get("TradeID", "").strip() or None,
    )


async def check_duplicate_trades(session: AsyncSession, fills: list[NormalizedFill]) -> set[int]:
    """
    检查填充列表中是否有重复的交易记录。
    返回重复记录在列表中的索引集合。
    """
    duplicate_indexes = set()
    
    # 收集所有非空的 source (TradeID) 和 order_id (OrderID)
    sources = []
    order_ids = []
    
    for i, fill in enumerate(fills):
        if fill.source:
            sources.append((fill.source, i))
        if fill.order_id:
            order_ids.append((fill.order_id, i))
    
    if sources:
        # 查询数据库中已存在的 TradeID
        source_values = [source for source, _ in sources]
        existing_sources_result = await session.execute(
            select(TradeFill.source).where(TradeFill.source.in_(source_values))
        )
        existing_sources = {row[0] for row in existing_sources_result.fetchall()}
        
        # 标记重复的记录索引
        for source, index in sources:
            if source in existing_sources:
                duplicate_indexes.add(index)
    
    if order_ids:
        # 查询数据库中已存在的 OrderID
        order_id_values = [order_id for order_id, _ in order_ids]
        existing_order_ids_result = await session.execute(
            select(TradeFill.order_id).where(TradeFill.order_id.in_(order_id_values))
        )
        existing_order_ids = {row[0] for row in existing_order_ids_result.fetchall()}
        
        # 标记重复的记录索引
        for order_id, index in order_ids:
            if order_id in existing_order_ids:
                duplicate_indexes.add(index)
    
    return duplicate_indexes


async def import_ibkr_csv(
    session: AsyncSession,
    file_bytes: bytes,
    filename: str,
) -> ImportBatch:
    csv_buffer = io.StringIO(file_bytes.decode("utf-8-sig"))
    reader = csv.DictReader(csv_buffer)
    if not reader.fieldnames:
        raise ImportValidationError("CSV header is missing")
    missing_columns = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
    if missing_columns:
        raise ImportValidationError(f"Missing required columns: {', '.join(missing_columns)}")

    fills: list[NormalizedFill] = []
    for idx, row in enumerate(reader, start=2):  # account for header line
        fills.append(_normalize_row(row, idx))

    if not fills:
        raise ImportValidationError("No trade rows found in file")

    # 检查重复的交易记录
    duplicate_indexes = await check_duplicate_trades(session, fills)
    
    # 过滤掉重复的记录
    unique_fills = [fill for i, fill in enumerate(fills) if i not in duplicate_indexes]
    skipped_count = len(duplicate_indexes)
    
    if not unique_fills:
        raise ImportValidationError("All trade records are duplicates - no new records to import")

    # 将数据库中未平仓的成交与新成交合并，确保聚合能够跨批次完成匹配
    combined_records: list[_CombinedFill] = []
    existing_parent_map: dict[int, ParentTrade] = {}

    asset_codes = {fill.asset_code for fill in unique_fills}
    if asset_codes:
        existing_parents_stmt = (
            select(ParentTrade)
            .join(Asset)
            .options(selectinload(ParentTrade.asset), selectinload(ParentTrade.fills))
            .where(Asset.code.in_(asset_codes), ParentTrade.close_time.is_(None))
        )
        result = await session.execute(existing_parents_stmt)
        existing_parents = result.scalars().unique().all()
        for parent in existing_parents:
            existing_parent_map[parent.id] = parent
            parent_timezone = parent.asset.timezone or "UTC"
            parent_exchange = parent.asset.exchange
            sorted_fills = sorted(parent.fills, key=lambda fill: fill.trade_time)
            for existing_fill in sorted_fills:
                normalized_existing = NormalizedFill(
                    asset_code=parent.asset.code,
                    asset_type=parent.asset.asset_type,
                    exchange=parent_exchange,
                    timezone=parent_timezone,
                    trade_time=existing_fill.trade_time,
                    side=existing_fill.side,
                    quantity=float(existing_fill.quantity),
                    price=float(existing_fill.price),
                    commission=float(existing_fill.commission),
                    currency=existing_fill.currency,
                    order_id=existing_fill.order_id,
                    source=existing_fill.source,
                )
                combined_records.append(
                    _CombinedFill(normalized=normalized_existing, kind="existing", existing_fill=existing_fill)
                )

    combined_records.extend(_CombinedFill(normalized=fill, kind="new") for fill in unique_fills)

    combined_normalized = [record.normalized for record in combined_records]
    aggregated_trades, _ = aggregate_parent_trades(combined_normalized)

    batch = ImportBatch(
        broker="ibkr",
        filename=filename,
        status=ImportStatus.PENDING,
        total_records=len(unique_fills),
        skipped_records=skipped_count,
        timezone="UTC",
    )
    session.add(batch)
    await session.flush()

    asset_cache: dict[str, Asset] = {}

    async def get_asset(symbol: str, asset_type: AssetType, timezone: str, exchange: str | None) -> Asset:
        if symbol in asset_cache:
            return asset_cache[symbol]
        result = await session.execute(select(Asset).where(Asset.code == symbol))
        asset = result.scalar_one_or_none()
        if asset is None:
            asset = Asset(code=symbol, asset_type=asset_type, timezone=timezone, exchange=exchange, name=symbol)
            session.add(asset)
            await session.flush()
        else:
            updated = False
            if not asset.exchange and exchange:
                asset.exchange = exchange
                updated = True
            if asset.timezone != timezone:
                asset.timezone = timezone
                updated = True
            if updated:
                await session.flush()
        asset_cache[symbol] = asset
        return asset

    fill_parent_lookup: dict[int, ParentTrade] = {}
    new_parent_trades: list[ParentTrade] = []

    for aggregated_trade in aggregated_trades:
        trade_fill_records = [combined_records[index] for index in aggregated_trade.fill_indexes]
        existing_parent_ids = {
            record.existing_fill.parent_trade_id
            for record in trade_fill_records
            if record.kind == "existing"
            and record.existing_fill is not None
            and record.existing_fill.parent_trade_id is not None
        }

        parent_model: ParentTrade
        if existing_parent_ids:
            if len(existing_parent_ids) > 1:
                raise ImportValidationError("Existing open fills from multiple parent trades cannot be merged automatically")
            parent_id = existing_parent_ids.pop()
            parent_model = existing_parent_map.get(parent_id)
            if parent_model is None:
                raise ImportValidationError("Referenced existing parent trade not found during aggregation")
            parent_model.direction = aggregated_trade.direction
            parent_model.quantity = aggregated_trade.quantity
            parent_model.open_time = aggregated_trade.open_time
            parent_model.close_time = aggregated_trade.close_time
            parent_model.open_price = aggregated_trade.open_price
            parent_model.close_price = aggregated_trade.close_price
            parent_model.total_commission = aggregated_trade.total_commission
            parent_model.profit_loss = aggregated_trade.profit_loss
            parent_model.currency = aggregated_trade.currency
        else:
            reference_fill = combined_records[aggregated_trade.fill_indexes[0]].normalized
            asset = await get_asset(
                reference_fill.asset_code,
                reference_fill.asset_type,
                reference_fill.timezone,
                reference_fill.exchange,
            )
            parent_model = ParentTrade(
                asset_id=asset.id,
                direction=aggregated_trade.direction,
                quantity=aggregated_trade.quantity,
                open_time=aggregated_trade.open_time,
                close_time=aggregated_trade.close_time,
                open_price=aggregated_trade.open_price,
                close_price=aggregated_trade.close_price,
                total_commission=aggregated_trade.total_commission,
                profit_loss=aggregated_trade.profit_loss,
                currency=aggregated_trade.currency,
            )
            session.add(parent_model)
            new_parent_trades.append(parent_model)

        for index in aggregated_trade.fill_indexes:
            fill_parent_lookup[index] = parent_model

    if new_parent_trades:
        await session.flush()

    for index, record in enumerate(combined_records):
        if record.kind == "existing":
            continue

        parent_model = fill_parent_lookup.get(index)
        if parent_model is None:
            raise ImportValidationError("Unable to determine parent trade for new fill")

        fill = record.normalized
        asset = await get_asset(fill.asset_code, fill.asset_type, fill.timezone, fill.exchange)
        trade_fill = TradeFill(
            parent_trade_id=parent_model.id,
            asset_id=asset.id,
            side=fill.side,
            quantity=fill.quantity,
            price=fill.price,
            commission=fill.commission,
            currency=fill.currency,
            trade_time=fill.trade_time,
            source=fill.source,
            order_id=fill.order_id,
            import_batch_id=batch.id,
        )
        session.add(trade_fill)

    batch.status = ImportStatus.COMPLETED
    batch.completed_at = datetime.utcnow()

    return batch
