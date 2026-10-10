"""NBU rates for the dates of marked foreign-currency income. Past rates never change: cached."""

from datetime import date

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
        changed = False
        for currency, days in needed.items():
            known = doc.rates.setdefault(currency, {})
            missing = days - set(known)
            if missing:
                known.update(self._nbu.rates(currency, min(missing), max(missing)))
                changed = True
        if changed:
            self._store.save(doc)
