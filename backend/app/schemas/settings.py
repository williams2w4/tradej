from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    timezone: str = Field(default="America/New_York")
    currency: str = Field(default="USD")


class SettingsUpdate(BaseModel):
    timezone: str | None = None
    currency: str | None = None
