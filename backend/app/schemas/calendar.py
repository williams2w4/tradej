from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class CalendarDay(BaseModel):
    date: date
    trade_count: int
    total_profit_loss: float
