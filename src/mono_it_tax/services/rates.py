"""NBU rates for the dates of marked foreign-currency income. Past rates never change: cached."""

from datetime import date
from decimal import Decimal

from mono_it_tax.clients.nbu import NbuClient
from mono_it_tax.config.enums import Currency
from mono_it_tax.store.year_store import YearStore


class RatesService:
    def __init__(self, nbu: NbuClient, store: YearStore) -> None:
        self._nbu = nbu
        self._store = store

    def ensure(self, year: int) -> None:
        """One request per currency (min..max of the missing dates) for marked, non-UAH payments."""
        doc = self._store.load(year)
        needed: dict[Currency, set[date]] = {}
        for payment_id in doc.marks:
            payment = doc.payments[payment_id]
            if payment.currency is not Currency.UAH:
                needed.setdefault(payment.currency, set()).add(payment.tax_date)
        fetched: dict[Currency, dict[date, Decimal]] = {}
        for currency, days in needed.items():
            missing = days - set(doc.rates.get(currency, {}))
            if missing:  # the network call stays outside the store lock
                fetched[currency] = self._nbu.rates(currency, min(missing), max(missing))
        if fetched:
            with self._store.edit(year) as current:  # merge: another request may have saved too
                for currency, rates in fetched.items():
                    current.rates.setdefault(currency, {}).update(rates)
