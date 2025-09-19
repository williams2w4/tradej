from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.core.currency import normalize_currency
from app.models import UserSetting
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
async def get_user_settings(db: AsyncSession = Depends(get_db)) -> SettingsRead:
    result = await db.execute(select(UserSetting).limit(1))
    setting = result.scalar_one_or_none()
    if setting is None:
        settings = get_settings()
        setting = UserSetting(timezone=settings.default_timezone, currency=normalize_currency(settings.default_currency))
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return SettingsRead(timezone=setting.timezone, currency=normalize_currency(setting.currency))


@router.patch("", response_model=SettingsRead)
async def update_user_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> SettingsRead:
    result = await db.execute(select(UserSetting).limit(1))
    setting = result.scalar_one_or_none()
    settings = get_settings()
    existing_timezone = setting.timezone if setting else settings.default_timezone
    existing_currency = setting.currency if setting else settings.default_currency

    timezone = payload.timezone or existing_timezone
    currency = payload.currency or existing_currency

    if setting is None:
        setting = UserSetting(timezone=timezone, currency=normalize_currency(currency))
        db.add(setting)
    else:
        setting.timezone = timezone
        setting.currency = normalize_currency(currency)
    await db.commit()
    await db.refresh(setting)
    return SettingsRead(timezone=setting.timezone, currency=normalize_currency(setting.currency))
