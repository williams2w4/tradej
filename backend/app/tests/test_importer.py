from __future__ import annotations

from datetime import timezone
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select

from app.models import ImportBatch, ParentTrade, TradeFill
from app.services.ibkr_importer import ImportValidationError, import_ibkr_csv


@pytest.mark.asyncio
async def test_import_ibkr_csv(async_session, mock_csv_bytes) -> None:
    batch = await import_ibkr_csv(async_session, mock_csv_bytes, "TradeNote.csv")
    await async_session.commit()

    assert batch.status.name == "COMPLETED"
    fills_result = await async_session.execute(select(TradeFill))
    fills = fills_result.scalars().all()
    trades_result = await async_session.execute(select(ParentTrade))
    trades = trades_result.scalars().all()
    batch_result = await async_session.execute(select(ImportBatch))
    batches = batch_result.scalars().all()

    assert len(fills) > 0
    assert len(trades) > 0
    assert len(batches) == 1

    first_fill = fills[0]
    assert first_fill.trade_time.tzinfo is not None
    assert first_fill.trade_time.utcoffset() == timezone.utc.utcoffset(first_fill.trade_time)

    # Parent trades should link to fills
    parent_fill_counts = {trade.id: 0 for trade in trades}
    for fill in fills:
        assert fill.parent_trade_id is not None
        parent_fill_counts[fill.parent_trade_id] += 1
    assert all(count > 0 for count in parent_fill_counts.values())

    tz = ZoneInfo("America/New_York")
    daily_profit: dict[str, float] = {}
    for trade in trades:
        if trade.close_time is None:
            continue
        close_date = trade.close_time.astimezone(tz).date().isoformat()
        daily_profit[close_date] = daily_profit.get(close_date, 0.0) + float(trade.profit_loss)

    expected_daily = {
        "2026-01-09": -77.38,
        "2026-01-12": 2.3,
        "2026-01-14": 662.25,
        "2026-01-15": 957.35,
        "2026-01-16": 28.57,
        "2026-01-17": 750.0,
    }
    for day, expected_value in expected_daily.items():
        assert day in daily_profit
        assert abs(daily_profit[day] - expected_value) <= 1.0


@pytest.mark.asyncio
async def test_import_binary_file_rejection(async_session) -> None:
    """Test that binary files like .numbers are properly rejected with helpful error messages."""
    # Simulate binary data that would cause UnicodeDecodeError
    binary_data = b'\x93\x94\x95\x96\x97\x98\x99\x9a'  # Invalid UTF-8 bytes
    
    with pytest.raises(ImportValidationError) as exc_info:
        await import_ibkr_csv(async_session, binary_data, "TradeNote.numbers")
    
    error_message = str(exc_info.value)
    assert "binary file format" in error_message
    assert "export your data as a CSV" in error_message


@pytest.mark.asyncio
async def test_import_invalid_encoding_rejection(async_session) -> None:
    """Test that files with encoding issues are properly rejected."""
    # Simulate data with encoding issues
    invalid_data = b'\x93\x94\x95\x96\x97\x98\x99\x9a'  # Invalid UTF-8 bytes
    
    with pytest.raises(ImportValidationError) as exc_info:
        await import_ibkr_csv(async_session, invalid_data, "TradeNote.csv")
    
    error_message = str(exc_info.value)
    assert "encoding issues" in error_message
    assert "UTF-8 encoded CSV" in error_message
