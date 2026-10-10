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
        """Cached accounts; one client-info request (counts toward the 60 s limit) when empty."""
        doc = self._store.load(year)
        if doc.accounts and not refresh:
            return doc.accounts
        doc.accounts = self._client.client_info().accounts
        self._store.save(doc)
        return doc.accounts

    def choose(self, year: int, account_ids: Sequence[str]) -> None:
        """Remember which accounts count for this tax year (one or many)."""
        doc = self._store.load(year)
        doc.tax_accounts = tuple(dict.fromkeys(account_ids))
        self._store.save(doc)
