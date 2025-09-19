from __future__ import annotations

from datetime import timezone

import pytest
from sqlalchemy import select

from app.models import ImportBatch, ParentTrade, TradeFill
from app.services.ibkr_importer import import_ibkr_csv


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
