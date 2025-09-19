from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.core.config import get_settings
from app.models import UserSetting
from app.schemas.settings import SettingsRead, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsRead)
async def get_user_settings(db: AsyncSession = Depends(get_db)) -> SettingsRead:
    result = await db.execute(select(UserSetting).limit(1))
    setting = result.scalar_one_or_none()
    if setting is None:
        default_timezone = get_settings().default_timezone
        setting = UserSetting(timezone=default_timezone)
        db.add(setting)
        await db.commit()
        await db.refresh(setting)
    return SettingsRead(timezone=setting.timezone)


@router.patch("", response_model=SettingsRead)
async def update_user_settings(
    payload: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> SettingsRead:
    result = await db.execute(select(UserSetting).limit(1))
    setting = result.scalar_one_or_none()
    if setting is None:
        setting = UserSetting(timezone=payload.timezone)
        db.add(setting)
    else:
        setting.timezone = payload.timezone
    await db.commit()
    await db.refresh(setting)
    return SettingsRead(timezone=setting.timezone)
