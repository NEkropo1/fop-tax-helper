"""Bank currency codes -> Currency. An unknown code fails loudly at the edge."""

from mono_it_tax.config.constants.currency import CURRENCY_BY_NUMERIC
from mono_it_tax.config.enums import Currency
from mono_it_tax.errors import UnsupportedCurrencyError


def currency_from_numeric(code: int) -> Currency:
    try:
        return CURRENCY_BY_NUMERIC[code]
    except KeyError:
        raise UnsupportedCurrencyError(code=code) from None
