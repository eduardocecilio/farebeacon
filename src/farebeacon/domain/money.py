from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from farebeacon.domain.exceptions import OfferValidationError

CURRENCY_EXPONENTS: dict[str, int] = {
    "BRL": 2,
    "EUR": 2,
    "GBP": 2,
    "JPY": 0,
    "KWD": 3,
    "USD": 2,
}


def currency_exponent(currency: str) -> int:
    try:
        return CURRENCY_EXPONENTS[currency.upper()]
    except KeyError as exc:
        raise OfferValidationError(
            "unsupported currency",
            details={"currency": currency.upper()},
        ) from exc


def decimal_to_minor(amount: Decimal, currency: str) -> int:
    if amount <= 0:
        raise OfferValidationError("price must be positive")
    exponent = currency_exponent(currency)
    quantum = Decimal(1).scaleb(-exponent)
    normalized = amount.quantize(quantum, rounding=ROUND_HALF_UP)
    return int(normalized.scaleb(exponent))


def minor_to_decimal(amount_minor: int, currency: str) -> Decimal:
    exponent = currency_exponent(currency)
    return Decimal(amount_minor).scaleb(-exponent)
