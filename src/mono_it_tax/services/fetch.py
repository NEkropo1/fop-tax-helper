"""Fetching incoming payments month by month, resumable and cancellable.

One request = one account x one uncovered range of one Kyiv month. Every answered request is saved
(payments + ledger record in ONE atomic document write, so coverage is never claimed without data).
"""

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime

from mono_it_tax.clients.monobank import MonobankClient
from mono_it_tax.clock import Clock
from mono_it_tax.config.constants.api import MONOBANK_MIN_INTERVAL_S
from mono_it_tax.config.enums import Currency, Scope
from mono_it_tax.domain.currency import currency_from_numeric
from mono_it_tax.domain.ledger import FetchRecord, missing_ranges
from mono_it_tax.domain.months import Month
from mono_it_tax.errors import UnknownAccountError
from mono_it_tax.services.accounts import AccountService
from mono_it_tax.store.document import YearDocument
from mono_it_tax.store.year_store import YearStore

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FetchTask:
    account_id: str
    month: Month
    start: datetime  # UTC
    end: datetime  # UTC, exclusive end of the uncovered range


@dataclass(frozen=True)
class FetchPlan:
    tasks: tuple[FetchTask, ...]

    @property
    def eta_seconds(self) -> float:
        """Conservative: the bank allows 1 request / 60 s per token."""
        return len(self.tasks) * MONOBANK_MIN_INTERVAL_S


@dataclass(frozen=True)
class FetchProgress:
    done: int
    total: int
    task: FetchTask


@dataclass(frozen=True)
class FetchOutcome:
    completed: int
    total: int
    cancelled: bool


class FetchService:
    def __init__(
        self, client: MonobankClient, accounts: AccountService, store: YearStore, clock: Clock
    ) -> None:
        self._client = client
        self._accounts = accounts
        self._store = store
        self._clock = clock

    @staticmethod
    def plan(doc: YearDocument, account_ids: Iterable[str], months: Sequence[Month]) -> FetchPlan:
        """Only the uncovered parts: already answered ranges cost nothing."""
        tasks = [
            FetchTask(account_id, month, start, end)
            for account_id in account_ids
            for month in months
            for start, end in missing_ranges(doc.ledger, account_id, month)
        ]
        return FetchPlan(tuple(tasks))

    def run(
        self,
        year: int,
        plan: FetchPlan,
        on_progress: Callable[[FetchProgress], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> FetchOutcome:
        """Execute the plan; cancellation is checked between requests, nothing answered is lost."""
        done = 0
        for task in plan.tasks:
            if should_cancel is not None and should_cancel():
                return FetchOutcome(done, len(plan.tasks), cancelled=True)
            self._fetch_one(year, task)
            done += 1
            if on_progress is not None:
                on_progress(FetchProgress(done, len(plan.tasks), task))
        return FetchOutcome(done, len(plan.tasks), cancelled=False)

    def _account_currency(self, year: int, account_id: str) -> Currency:
        """Statement amounts are in the account currency, so the account must be known (cached
        accounts cost nothing; otherwise one client-info request)."""
        for account in self._accounts.accounts(year):
            if account.id == account_id:
                return currency_from_numeric(account.currency_code)
        raise UnknownAccountError

    def _fetch_one(self, year: int, task: FetchTask) -> None:
        currency = self._account_currency(year, task.account_id)
        result = self._client.statement(task.account_id, currency, task.start, task.end)
        doc = self._store.load(year)
        for payment in result.incoming:
            doc.payments[payment.id] = payment
        doc.ledger.append(
            FetchRecord(
                account_id=task.account_id,
                requested_from=task.start,
                requested_to=task.end,
                fetched_at=self._clock.now(),
                items_received=result.items_received,
                items_kept=len(result.incoming),
                scope=Scope.INCOMING_ONLY,
            )
        )
        self._store.save(doc)
        log.info(
            "fetched %s: %d items, %d incoming kept",
            task.month,
            result.items_received,
            len(result.incoming),
        )
