"""The user's accounts: fetched once from client-info, cached in the year document."""

from collections.abc import Sequence

from mono_it_tax.clients.monobank import MonobankClient
from mono_it_tax.domain.account import Account
from mono_it_tax.store.year_store import YearStore


class AccountService:
    def __init__(self, client: MonobankClient, store: YearStore) -> None:
        self._client = client
        self._store = store

    def accounts(self, year: int, *, refresh: bool = False) -> tuple[Account, ...]:
        """The user's accounts. One client-info request (counts toward the 60 s limit) only for a
        first run or an explicit refresh, which updates just this year's cache. A year that has no
        cache of its own reads (never copies) the list of another stored year."""
        if not refresh:
            cached = self._cached(year)
            if cached:
                return cached
        fresh = self._client.client_info().accounts  # slow (throttle): never inside a store lock
        with self._store.edit(year) as doc:
            doc.accounts = fresh
        return fresh

    def _cached(self, year: int) -> tuple[Account, ...]:
        own = self._store.load(year).accounts
        if own:
            return own
        for other in sorted(self._store.years(), reverse=True):
            if other != year and (shared := self._store.load(other).accounts):
                return shared
        return ()

    def choose(self, year: int, account_ids: Sequence[str]) -> None:
        """Remember which accounts count for this tax year (one or many)."""
        with self._store.edit(year) as doc:
            doc.tax_accounts = tuple(dict.fromkeys(account_ids))
