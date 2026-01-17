from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from sqlalchemy import select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import (
    Asset,
    ImportBatch,
    ImportStatus,
    ParentTrade,
    TradeFill,
)
from app.models.enums import AssetType, FillSide
from app.services.aggregation import NormalizedFill, aggregate_parent_trades, resolve_net_cash


@dataclass
class _CombinedFill:
    normalized: NormalizedFill
    kind: Literal["existing", "new"]
    existing_fill: TradeFill | None = None

BROKER_TIMEZONE = "America/New_York"

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
    "NetCash",
}


class ImportValidationError(Exception):
    def __init__(self, message: str, row_number: int | None = None) -> None:
        if row_number is not None:
            super().__init__(f"Row {row_number}: {message}")
        else:
            super().__init__(message)


class DuplicateTradeError(ImportValidationError):
    def __init__(self, message: str, duplicate_count: int) -> None:
        super().__init__(message)
        self.duplicate_count = duplicate_count


def _infer_multiplier(symbol: str, asset_type: AssetType) -> float:
    """Infer contract multiplier based on symbol and asset type."""
    if asset_type != AssetType.FUTURE:
        return 1.0
    
    # Common futures multipliers
    if symbol.startswith("ES"):
        return 50.0  # E-mini S&P 500
    elif symbol.startswith("MES"):
        return 5.0   # Micro E-mini S&P 500
    elif symbol.startswith("NQ"):
        return 20.0  # E-mini NASDAQ-100
    elif symbol.startswith("MNQ"):
        return 2.0   # Micro E-mini NASDAQ-100
    elif symbol.startswith("YM"):
        return 5.0   # E-mini Dow Jones
    elif symbol.startswith("MYM"):
        return 0.5   # Micro E-mini Dow Jones
    elif symbol.startswith("RTY"):
        return 50.0  # E-mini Russell 2000
    elif symbol.startswith("M2K"):
        return 5.0   # Micro E-mini Russell 2000
    elif symbol.startswith("GC"):
        return 100.0 # Gold futures
    elif symbol.startswith("MGC"):
        return 10.0  # Micro Gold futures
    elif symbol.startswith("SI"):
        return 5000.0 # Silver futures
    elif symbol.startswith("SIL"):
        return 1000.0 # Micro Silver futures
    elif symbol.startswith("CL"):
        return 1000.0 # Crude Oil futures
    elif symbol.startswith("MCL"):
        return 100.0  # Micro Crude Oil futures
    else:
        return 1.0   # Default multiplier for unknown futures


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

    # Handle contract multiplier for futures
    try:
        multiplier = float(row.get("Multiplier", "0"))
    except (ValueError, TypeError):
        multiplier = 0.0
    
    # If multiplier is missing or invalid, infer it from symbol
    if multiplier <= 0 and asset_type == AssetType.FUTURE:
        multiplier = _infer_multiplier(symbol, asset_type)
    
    # Default to 1.0 if still invalid (e.g. not a future or inference failed)
    if multiplier <= 0:
        multiplier = 1.0

    # Handle Proceeds if available (IBKR usually provides this)
    # Proceeds is the net cash flow (excluding commission usually, but check broker spec)
    # We store the absolute value of the transaction amount
    proceeds = None
    if "Proceeds" in row and row["Proceeds"]:
        try:
            proceeds = abs(float(row["Proceeds"]))
        except (ValueError, TypeError):
            pass

    try:
        net_cash = float(row["NetCash"])
    except (ValueError, TypeError) as exc:
        raise ImportValidationError("NetCash must be a number", row_number) from exc

    exchange_field = row.get("ListingExchange", "")
    exchange = exchange_field.split(",")[0].split(";")[0].strip().upper() or None
    timezone = BROKER_TIMEZONE
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
        multiplier=multiplier,
        proceeds=proceeds,
        net_cash=net_cash,
        order_id=row.get("OrderID", "").strip() or None,
        source=row.get("TradeID", "").strip() or None,
    )


async def check_duplicate_trades(session: AsyncSession, fills: list[NormalizedFill]) -> set[int]:
    """
    检查填充列表中是否有重复的交易记录。
    当交易时间一致且 TradeID 已存在时视为重复。
    返回重复记录在列表中的索引集合。
    """
    duplicate_indexes = set()

    # 收集所有非空的 source (TradeID)
    sources: dict[str, list[int]] = {}

    for index, fill in enumerate(fills):
        if fill.source:
            sources.setdefault(fill.source, []).append(index)

    if sources:
        source_values = list(sources.keys())
        existing_sources_result = await session.execute(
            select(TradeFill.source, TradeFill.trade_time).where(TradeFill.source.in_(source_values))
        )
        existing_sources: dict[str, set[datetime]] = {}
        for existing_source, trade_time in existing_sources_result.all():
            if existing_source is None or trade_time is None:
                continue
            existing_sources.setdefault(existing_source, set()).add(trade_time)

        for source, indexes in sources.items():
            known_times = existing_sources.get(source)
            if not known_times:
                continue
            for index in indexes:
                if fills[index].trade_time in known_times:
                    duplicate_indexes.add(index)

    return duplicate_indexes


async def remove_existing_duplicate_trades(session: AsyncSession, duplicate_fills: list[NormalizedFill]) -> None:
    """
    删除数据库中与传入成交记录相同（TradeID + 时间）的父交易。
    """
    keys = {(fill.source, fill.trade_time) for fill in duplicate_fills if fill.source}
    if not keys:
        return

    key_values = list(keys)
    stmt = select(TradeFill).where(
        tuple_(TradeFill.source, TradeFill.trade_time).in_(key_values)
    )
    result = await session.execute(stmt)
    existing_fills = result.scalars().all()
    if not existing_fills:
        return

    parent_ids = {fill.parent_trade_id for fill in existing_fills if fill.parent_trade_id is not None}
    if parent_ids:
        parent_stmt = select(ParentTrade).where(ParentTrade.id.in_(parent_ids))
        parents = (await session.execute(parent_stmt)).scalars().unique().all()
        for parent in parents:
            await session.delete(parent)
    else:
        for fill in existing_fills:
            await session.delete(fill)


async def import_ibkr_csv(
    session: AsyncSession,
    file_bytes: bytes,
    filename: str,
    override_duplicates: bool = False,
) -> ImportBatch:
    try:
        csv_buffer = io.StringIO(file_bytes.decode("utf-8-sig"))
    except UnicodeDecodeError as e:
        # Check if this might be a binary file based on the filename
        if filename and any(filename.lower().endswith(ext) for ext in ['.numbers', '.xlsx', '.xls']):
            raise ImportValidationError(
                f"Cannot import '{filename}' as it appears to be a binary file format. "
                "Please export your data as a CSV file and try again."
            ) from e
        else:
            raise ImportValidationError(
                f"Unable to read file '{filename}' - it may not be a valid CSV file or may have encoding issues. "
                "Please ensure the file is saved as UTF-8 encoded CSV."
            ) from e
    
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

    if duplicate_indexes and override_duplicates:
        await remove_existing_duplicate_trades(session, [fills[i] for i in duplicate_indexes])
        unique_fills = fills
        skipped_count = 0
    else:
        # 过滤掉重复的记录
        unique_fills = [fill for i, fill in enumerate(fills) if i not in duplicate_indexes]
        skipped_count = len(duplicate_indexes)

        if not unique_fills:
            raise DuplicateTradeError("All trade records are duplicates - no new records to import", skipped_count)

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
                # Infer multiplier for existing fills based on symbol and asset type
                multiplier = _infer_multiplier(parent.asset.code, parent.asset.asset_type)
                
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
                    multiplier=multiplier,
                    order_id=existing_fill.order_id,
                    source=existing_fill.source,
                    net_cash=float(existing_fill.net_cash) if existing_fill.net_cash is not None else None,
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
            net_cash=resolve_net_cash(fill),
        )
        session.add(trade_fill)

    batch.status = ImportStatus.COMPLETED
    batch.completed_at = datetime.utcnow()

    return batch
