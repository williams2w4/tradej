from __future__ import annotations

from decimal import Decimal

SUPPORTED_CURRENCIES = {"USD", "HKD", "EUR", "JPY", "CNY"}

# Rates represent how many units of the target currency equal one US dollar.
RATES_PER_USD: dict[str, Decimal] = {
    "USD": Decimal("1"),
    "HKD": Decimal("7.80"),
    "EUR": Decimal("0.92"),
    "JPY": Decimal("145.00"),
    "CNY": Decimal("7.10"),
}


def normalize_currency(code: str | None) -> str:
    if not code:
        return "USD"
    upper = code.upper()
    if upper == "RMB":
        return "CNY"
    return upper


def convert_amount(value: float | int | Decimal, from_currency: str | None, to_currency: str | None) -> Decimal:
    amount = Decimal(str(value))
    from_code = normalize_currency(from_currency)
    to_code = normalize_currency(to_currency)

    if from_code not in RATES_PER_USD or to_code not in RATES_PER_USD:
        return amount

    if from_code == to_code:
        return amount

    usd_value = amount / RATES_PER_USD[from_code]
    return usd_value * RATES_PER_USD[to_code]
