from __future__ import annotations

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

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

    aggregated_trades, _ = aggregate_parent_trades(unique_fills)

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

    parent_models: list[tuple[list[int], ParentTrade]] = []
    for trade in aggregated_trades:
        first_fill = unique_fills[trade.fill_indexes[0]]
        asset = await get_asset(first_fill.asset_code, first_fill.asset_type, first_fill.timezone, first_fill.exchange)
        parent = ParentTrade(
            asset_id=asset.id,
            direction=trade.direction,
            quantity=trade.quantity,
            open_time=trade.open_time,
            close_time=trade.close_time,
            open_price=trade.open_price,
            close_price=trade.close_price,
            total_commission=trade.total_commission,
            profit_loss=trade.profit_loss,
            currency=trade.currency,
        )
        session.add(parent)
        parent_models.append((trade.fill_indexes, parent))

    await session.flush()

    parent_id_lookup: dict[int, int] = {}
    for fill_indexes, parent in parent_models:
        for fill_index in fill_indexes:
            parent_id_lookup[fill_index] = parent.id

    for idx, fill in enumerate(unique_fills):
        asset = await get_asset(fill.asset_code, fill.asset_type, fill.timezone, fill.exchange)
        trade_fill = TradeFill(
            parent_trade_id=parent_id_lookup.get(idx),
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
