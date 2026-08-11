from decimal import Decimal

import pytest

from farebeacon.domain.exceptions import OfferValidationError
from farebeacon.domain.money import decimal_to_minor, minor_to_decimal


def test_money_uses_currency_exponent() -> None:
    assert decimal_to_minor(Decimal("123.45"), "BRL") == 12345
    assert decimal_to_minor(Decimal(123), "JPY") == 123
    assert decimal_to_minor(Decimal("1.234"), "KWD") == 1234
    assert minor_to_decimal(12345, "BRL") == Decimal("123.45")


def test_money_rejects_unknown_currency_and_nonpositive_amount() -> None:
    with pytest.raises(OfferValidationError):
        decimal_to_minor(Decimal(10), "ZZZ")
    with pytest.raises(OfferValidationError):
        decimal_to_minor(Decimal(0), "BRL")
