"""ISO 4217 numeric codes the bank uses -> our Currency enum."""

from mono_it_tax.config.enums import Currency

CURRENCY_BY_NUMERIC: dict[int, Currency] = {
    980: Currency.UAH,
    840: Currency.USD,
    978: Currency.EUR,
    826: Currency.GBP,
    985: Currency.PLN,
}
