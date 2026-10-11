"""Marked income: which payments the human counts, with optional amount corrections, in UAH.

Each receipt is converted at the NBU rate of its own date and rounded to kopiykas right there
(`round_money`); that rounded value is the income entry. Period income is the exact sum of the
entries, and taxes are rounded once from that sum.
"""

from collections.abc import Mapping
from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, field_validator

from mono_it_tax.config.enums import Currency
from mono_it_tax.domain.money import minor_to_decimal, round_money
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
    """UAH income entry for one receipt: NBU rate on the date of receipt (Kyiv), rounded to
    kopiykas per receipt. A missing rate is an error, never a guess. A UAH amount is rounded too, so
    a corrected amount with extra digits cannot leak into the sum."""
    if currency is Currency.UAH:
        return round_money(amount)
    try:
        return round_money(amount * rates[currency][on])
    except KeyError:
        raise RateMissingError(currency=currency.value, date=on.isoformat()) from None


def income_uah(payment: Payment, mark: Mark, rates: Rates) -> Decimal:
    """The receipt's income entry: UAH, already rounded to kopiykas (see `to_uah`)."""
    return to_uah(counted_amount(payment, mark), payment.currency, payment.tax_date, rates)
