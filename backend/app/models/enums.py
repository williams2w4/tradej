from __future__ import annotations

from enum import Enum as PyEnum


class AssetType(str, PyEnum):
    STOCK = "stock"
    OPTION = "option"
    FUTURE = "future"


class TradeDirection(str, PyEnum):
    LONG = "long"
    SHORT = "short"


class FillSide(str, PyEnum):
    BUY = "BUY"
    SELL = "SELL"
