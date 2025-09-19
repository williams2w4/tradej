from __future__ import annotations

from pydantic import BaseModel, Field


class SettingsRead(BaseModel):
    timezone: str = Field(default="America/New_York")


class SettingsUpdate(BaseModel):
    timezone: str
