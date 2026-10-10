"""Marked income: which payments the human counts, with optional amount corrections, in UAH."""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from mono_it_tax.config.enums import Currency
from mono_it_tax.domain.money import minor_to_decimal
from mono_it_tax.domain.payment import Payment
from mono_it_tax.errors import RateMissingError

Rates = Mapping[Currency, Mapping[date, Decimal]]


class Mark(BaseModel):
    """The user counts this payment as income, by payment id, optionally correcting the amount."""

    model_config = ConfigDict(frozen=True)

    payment_id: str
    amount_override: Decimal | None = None  # major units, in the payment's currency

    @field_validator("amount_override")
    @classmethod
    def _positive(cls, v: Decimal | None) -> Decimal | None:
        if v is not None and v <= 0:
            raise ValueError("amount_override must be positive")
        return v


def counted_amount(payment: Payment, mark: Mark) -> Decimal:
    """Major units in the payment's own currency."""
    if mark.amount_override is not None:
        return mark.amount_override
    return minor_to_decimal(payment.amount)


def to_uah(amount: Decimal, currency: Currency, on: date, rates: Rates) -> Decimal:
    """NBU rate on the date of receipt (Kyiv); a missing rate is an error, never a guess."""
    if currency is Currency.UAH:
        return amount
    try:
        return amount * rates[currency][on]
    except KeyError:
        raise RateMissingError(currency=currency.value, date=on.isoformat()) from None


def income_uah(payment: Payment, mark: Mark, rates: Rates) -> Decimal:
    return to_uah(counted_amount(payment, mark), payment.currency, payment.tax_date, rates)
