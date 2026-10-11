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
        """The user's accounts, which do not depend on the tax year: the cache of any stored year
        serves them. One client-info request (counts toward the 60 s limit) only for a first run or
        an explicit refresh; a refresh updates every stored year so they never disagree."""
        if not refresh:
            cached = self._cached(year)
            if cached:
                self._remember(year, cached)
                return cached
        fresh = self._client.client_info().accounts  # slow (throttle): never inside a store lock
        for stored in {*self._store.years(), year}:
            self._remember(stored, fresh, replace=True)
        return fresh

    def _cached(self, year: int) -> tuple[Account, ...]:
        own = self._store.load(year).accounts
        if own:
            return own
        for other in sorted(self._store.years(), reverse=True):
            if other != year and (shared := self._store.load(other).accounts):
                return shared
        return ()

    def _remember(self, year: int, accounts: tuple[Account, ...], *, replace: bool = False) -> None:
        with self._store.edit(year) as doc:
            if replace or not doc.accounts:
                doc.accounts = accounts

    def choose(self, year: int, account_ids: Sequence[str]) -> None:
        """Remember which accounts count for this tax year (one or many)."""
        with self._store.edit(year) as doc:
            doc.tax_accounts = tuple(dict.fromkeys(account_ids))
