from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection


def apply_schema_migrations(connection: Connection) -> None:
    """
    Apply lightweight schema migrations that are safe to run on every startup.
    Currently ensures the trade_fills.net_cash column exists so new imports
    can persist broker-provided NetCash values.
    """
    inspector = inspect(connection)
    columns = {column["name"] for column in inspector.get_columns("trade_fills")}
    if "net_cash" not in columns:
        connection.execute(text("ALTER TABLE trade_fills ADD COLUMN net_cash NUMERIC(20, 8)"))
