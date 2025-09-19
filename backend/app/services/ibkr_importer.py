from __future__ import annotations

import csv
import io
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
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

    aggregated_trades, _ = aggregate_parent_trades(fills)

    batch = ImportBatch(
        broker="ibkr",
        filename=filename,
        status=ImportStatus.PENDING,
        total_records=len(fills),
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
        first_fill = fills[trade.fill_indexes[0]]
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

    for idx, fill in enumerate(fills):
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
