from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from app.models.enums import AssetType, FillSide, TradeDirection


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
    multiplier: float = 1.0  # Contract multiplier, defaults to 1.0 for stocks
    proceeds: float | None = None  # Absolute transaction amount (excluding commission)
    order_id: str | None = None
    source: str | None = None
    net_cash: float | None = None


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


def resolve_net_cash(fill: NormalizedFill) -> float:
    """
    Return the per-fill net cash amount. Falls back to calculating from price/quantity
    if explicit NetCash is not available.
    """
    if fill.net_cash is not None:
        return float(fill.net_cash)
    transaction_amount = float(fill.price) * float(fill.quantity) * float(fill.multiplier)
    signed_amount = transaction_amount if fill.side == FillSide.SELL else -transaction_amount
    return signed_amount - float(fill.commission)


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
                "net_cash_total": 0.0,
                "max_abs_position": 0.0,
                "currency": fill.currency,
                "multiplier": fill.multiplier,  # Store multiplier from the fill
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

        # Calculate transaction amount (absolute value)
        # Use proceeds if available, otherwise calculate from price * quantity * multiplier
        if fill.proceeds is not None:
            transaction_amount = abs(fill.proceeds)
            # If using proceeds, we need to derive the effective unit price for average price calculations
            # effective_unit_price = transaction_amount / (fill.quantity * fill.multiplier)
            # But here we just need the total amount for the portion of quantity
            
            # Pro-rate amount based on quantity if needed (though usually fill is processed as a whole)
            # In this loop, we process one fill at a time, so transaction_amount corresponds to fill.quantity
            unit_amount = transaction_amount / fill.quantity if fill.quantity > 0 else 0
        else:
            transaction_amount = float(fill.price) * float(fill.quantity) * float(fill.multiplier)
            unit_amount = float(fill.price) * float(fill.multiplier)

        if open_qty > 0:
            state["open_sum_qty"] += open_qty
            state["open_sum_amount"] += open_qty * unit_amount

        if close_qty > 0:
            state["close_sum_qty"] += close_qty
            state["close_sum_amount"] += close_qty * unit_amount

        state["net_cash_total"] += resolve_net_cash(fill)

        state["total_commission"] += float(fill.commission)
        state["position"] = position_after
        state["max_abs_position"] = max(state["max_abs_position"], abs_after)

        if position_after == 0:
            open_price = (
                float(state["open_sum_amount"]) / (float(state["open_sum_qty"]) * float(fill.multiplier))
                if state["open_sum_qty"] > 0
                else None
            )
            close_price = (
                float(state["close_sum_amount"]) / (float(state["close_sum_qty"]) * float(fill.multiplier))
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
                    profit_loss=float(state["net_cash_total"]),
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
        multiplier = float(state["multiplier"])
        open_price = (
            float(state["open_sum_amount"]) / (float(state["open_sum_qty"]) * multiplier)
            if state["open_sum_qty"] > 0
            else None
        )
        close_price = (
            float(state["close_sum_amount"]) / (float(state["close_sum_qty"]) * multiplier)
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
                profit_loss=float(state["net_cash_total"]),
                currency=state["currency"],
                fill_indexes=list(state["fills"]),
            )
        )
        for fill_index in state["fills"]:
            fill_to_parent[fill_index] = parent_index

    return parent_trades, fill_to_parent
