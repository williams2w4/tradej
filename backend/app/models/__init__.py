from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - only for static analysis
    from app.models.asset import Asset
    from app.models.enums import AssetType, FillSide, TradeDirection
    from app.models.import_batch import ImportBatch, ImportStatus
    from app.models.trade import ParentTrade, TradeFill
    from app.models.user_setting import UserSetting

__all__ = [
    "Asset",
    "AssetType",
    "ImportBatch",
    "ImportStatus",
    "ParentTrade",
    "TradeDirection",
    "TradeFill",
    "FillSide",
    "UserSetting",
]


def __getattr__(name: str) -> Any:  # pragma: no cover - runtime convenience imports
    if name == "Asset":
        from app.models.asset import Asset as _Asset

        return _Asset
    if name in {"AssetType", "FillSide", "TradeDirection"}:
        from app.models.enums import AssetType as _AssetType, FillSide as _FillSide, TradeDirection as _TradeDirection

        mapping = {
            "AssetType": _AssetType,
            "FillSide": _FillSide,
            "TradeDirection": _TradeDirection,
        }
        return mapping[name]
    if name in {"ImportBatch", "ImportStatus"}:
        from app.models.import_batch import ImportBatch as _ImportBatch, ImportStatus as _ImportStatus

        mapping = {"ImportBatch": _ImportBatch, "ImportStatus": _ImportStatus}
        return mapping[name]
    if name in {"ParentTrade", "TradeFill"}:
        from app.models.trade import ParentTrade as _ParentTrade, TradeFill as _TradeFill

        mapping = {"ParentTrade": _ParentTrade, "TradeFill": _TradeFill}
        return mapping[name]
    if name == "UserSetting":
        from app.models.user_setting import UserSetting as _UserSetting

        return _UserSetting
    raise AttributeError(f"module 'app.models' has no attribute {name}")
