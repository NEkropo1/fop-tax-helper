"""The human's decisions: which payments are income, amount corrections, 'this month is done'."""

from collections.abc import Iterable
from decimal import Decimal

from mono_it_tax.clock import Clock
from mono_it_tax.config.enums import MonthState
from mono_it_tax.domain.income import Mark
from mono_it_tax.domain.months import Month, month_of
from mono_it_tax.domain.payment import Payment
from mono_it_tax.domain.states import Review, can_transition, month_state
from mono_it_tax.store.document import YearDocument
from mono_it_tax.store.year_store import YearStore


def month_payments(doc: YearDocument, account_id: str, month: Month) -> tuple[Payment, ...]:
    """Incoming payments of one account whose Kyiv tax date falls in `month`, oldest first."""
    found = [
        p
        for p in doc.payments.values()
        if p.account_id == account_id and month_of(p.tax_date) == month
    ]
    return tuple(sorted(found, key=lambda p: (p.time, p.id)))


def state_of(doc: YearDocument, account_id: str, month: Month) -> MonthState:
    ids = frozenset(p.id for p in month_payments(doc, account_id, month))
    review = next(
        (
            r
            for r in doc.reviews
            if (r.account_id, r.year, r.month) == (account_id, month.year, month.month)
        ),
        None,
    )
    return month_state(doc.ledger, review, ids, account_id, month)


class MarkingService:
    def __init__(self, store: YearStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def mark(self, year: int, payment_ids: Iterable[str]) -> None:
        doc = self._store.load(year)
        for payment_id in payment_ids:
            if payment_id not in doc.payments:
                raise KeyError(payment_id)
            doc.marks.setdefault(payment_id, Mark(payment_id=payment_id))
        self._store.save(doc)

    def unmark(self, year: int, payment_ids: Iterable[str]) -> None:
        doc = self._store.load(year)
        for payment_id in payment_ids:
            doc.marks.pop(payment_id, None)
        self._store.save(doc)

    def set_amount(self, year: int, payment_id: str, amount: Decimal | None) -> None:
        """Correct the counted amount (major units); None removes the correction. Must be marked."""
        doc = self._store.load(year)
        if payment_id not in doc.marks:
            raise KeyError(payment_id)
        doc.marks[payment_id] = Mark(payment_id=payment_id, amount_override=amount)
        self._store.save(doc)

    def unreview_month(self, year: int, account_id: str, month: Month) -> None:
        """Reopen a confirmed account-month for changes (no-op when it was not confirmed)."""
        doc = self._store.load(year)
        kept = [
            r
            for r in doc.reviews
            if (r.account_id, r.year, r.month) != (account_id, month.year, month.month)
        ]
        if len(kept) != len(doc.reviews):
            doc.reviews = kept
            self._store.save(doc)

    def review_month(self, year: int, account_id: str, month: Month) -> None:
        """'Income marked, done' for one account-month; only for a fully fetched month."""
        doc = self._store.load(year)
        old = state_of(doc, account_id, month)
        if not can_transition(old, MonthState.REVIEWED):
            raise ValueError(f"cannot review a month in state {old}")
        ids = tuple(sorted(p.id for p in month_payments(doc, account_id, month)))
        doc.reviews = [
            r
            for r in doc.reviews
            if (r.account_id, r.year, r.month) != (account_id, month.year, month.month)
        ]
        doc.reviews.append(
            Review(
                account_id=account_id,
                year=month.year,
                month=month.month,
                payment_ids=ids,
                reviewed_at=self._clock.now(),
            )
        )
        self._store.save(doc)
