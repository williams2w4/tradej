from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from app.models.asset import AssetType
from app.models.trade import FillSide, TradeDirection


@dataclass
class NormalizedFill:
    asset_code: str
    asset_type: AssetType
    exchange: str | None
    timezone: str
    trade_time: datetime
    side: FillSide
    quantity: float
    price: float
    commission: float
    currency: str
    order_id: str | None = None
    source: str | None = None


@dataclass
class AggregatedTrade:
    asset_code: str
    asset_type: AssetType
    direction: TradeDirection
    quantity: float
    open_time: datetime
    close_time: datetime | None
    open_price: float | None
    close_price: float | None
    total_commission: float
    profit_loss: float
    currency: str
    fill_indexes: list[int] = field(default_factory=list)


def aggregate_parent_trades(fills: Iterable[NormalizedFill]) -> tuple[list[AggregatedTrade], dict[int, int]]:
    ordered_fills = sorted(enumerate(fills), key=lambda item: item[1].trade_time)
    fill_lookup = {index: fill for index, fill in ordered_fills}
    parent_trades: list[AggregatedTrade] = []
    fill_to_parent: dict[int, int] = {}
    state_by_asset: dict[str, dict] = {}

    for index, fill in ordered_fills:
        state = state_by_asset.get(fill.asset_code)
        signed_qty = fill.quantity if fill.side == FillSide.BUY else -fill.quantity

        if state is None or state.get("position", 0.0) == 0:
            direction = TradeDirection.LONG if signed_qty > 0 else TradeDirection.SHORT
            state = {
                "direction": direction,
                "asset_code": fill.asset_code,
                "asset_type": fill.asset_type,
                "position": 0.0,
                "open_time": fill.trade_time,
                "fills": [],
                "open_sum_qty": 0.0,
                "open_sum_amount": 0.0,
                "close_sum_qty": 0.0,
                "close_sum_amount": 0.0,
                "total_commission": 0.0,
                "cash_flow": 0.0,
                "max_abs_position": 0.0,
                "currency": fill.currency,
            }
            state_by_asset[fill.asset_code] = state

        state["fills"].append(index)
        position_before = state["position"]
        position_after = position_before + signed_qty
        abs_before = abs(position_before)
        abs_after = abs(position_after)

        open_qty = 0.0
        close_qty = 0.0
        if position_before == 0:
            open_qty = abs(signed_qty)
        elif position_before * position_after >= 0:
            if abs_after > abs_before:
                open_qty = abs_after - abs_before
            elif abs_after < abs_before:
                close_qty = abs_before - abs_after
        else:
            close_qty = abs_before
            open_qty = abs_after

        if open_qty > 0:
            state["open_sum_qty"] += open_qty
            state["open_sum_amount"] += open_qty * float(fill.price)

        if close_qty > 0:
            state["close_sum_qty"] += close_qty
            state["close_sum_amount"] += close_qty * float(fill.price)

        if signed_qty > 0:
            state["cash_flow"] -= float(fill.price) * float(fill.quantity)
        else:
            state["cash_flow"] += float(fill.price) * float(fill.quantity)

        state["total_commission"] += float(fill.commission)
        state["position"] = position_after
        state["max_abs_position"] = max(state["max_abs_position"], abs_after)

        if position_after == 0:
            open_price = (
                float(state["open_sum_amount"]) / float(state["open_sum_qty"])
                if state["open_sum_qty"] > 0
                else None
            )
            close_price = (
                float(state["close_sum_amount"]) / float(state["close_sum_qty"])
                if state["close_sum_qty"] > 0
                else None
            )
            parent_index = len(parent_trades)
            parent_trades.append(
                AggregatedTrade(
                    asset_code=state["asset_code"],
                    asset_type=state["asset_type"],
                    direction=state["direction"],
                    quantity=float(state["max_abs_position"]),
                    open_time=state["open_time"],
                    close_time=fill.trade_time,
                    open_price=open_price,
                    close_price=close_price,
                    total_commission=float(state["total_commission"]),
                    profit_loss=float(state["cash_flow"]) - float(state["total_commission"]),
                    currency=state["currency"],
                    fill_indexes=list(state["fills"]),
                )
            )
            for fill_index in state["fills"]:
                fill_to_parent[fill_index] = parent_index
            state_by_asset.pop(fill.asset_code, None)
        else:
            state_by_asset[fill.asset_code] = state

    for state in state_by_asset.values():
        open_price = (
            float(state["open_sum_amount"]) / float(state["open_sum_qty"])
            if state["open_sum_qty"] > 0
            else None
        )
        close_price = (
            float(state["close_sum_amount"]) / float(state["close_sum_qty"])
            if state["close_sum_qty"] > 0
            else None
        )
        parent_index = len(parent_trades)
        parent_trades.append(
            AggregatedTrade(
                asset_code=state["asset_code"],
                asset_type=state["asset_type"],
                direction=state["direction"],
                quantity=float(state["max_abs_position"]) or abs(float(state["position"])),
                open_time=state["open_time"],
                close_time=None,
                open_price=open_price,
                close_price=close_price,
                total_commission=float(state["total_commission"]),
                profit_loss=float(state["cash_flow"]) - float(state["total_commission"]),
                currency=state["currency"],
                fill_indexes=list(state["fills"]),
            )
        )
        for fill_index in state["fills"]:
            fill_to_parent[fill_index] = parent_index

    return parent_trades, fill_to_parent
