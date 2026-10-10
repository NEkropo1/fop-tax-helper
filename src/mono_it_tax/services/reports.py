"""Numbers from the user's decisions: indicative estimate for months, and declaration rows.

Previous period for declaration help comes from one of two paths:
  A. typed by the user from the filed declaration (stored as MANUAL; wins when it exists), or
  B. computed from the stored, marked income of every earlier quarter (COMPUTED).
"""

from collections.abc import Collection, Sequence
from datetime import datetime
from decimal import Decimal

from mono_it_tax.clock import Clock
from mono_it_tax.config.enums import MarkSource, MonthState, Period
from mono_it_tax.config.rules import Rules
from mono_it_tax.domain.declaration import (
    ZERO,
    DeclarationRows,
    PreviousDeclaration,
    build_declaration,
    validate_previous_rows,
)
from mono_it_tax.domain.estimate import Estimate, estimate
from mono_it_tax.domain.income import income_uah
from mono_it_tax.domain.months import Month, month_of, months_between
from mono_it_tax.domain.periods import (
    MonthsSelection,
    increment_months,
    last_month,
    previous_period,
)
from mono_it_tax.errors import MonthsNotReviewedError
from mono_it_tax.services.marking import state_of
from mono_it_tax.store.document import DeclarationInput, YearDocument
from mono_it_tax.store.year_store import YearStore

PERIOD_CHAIN = (Period.Q1, Period.H1, Period.M9, Period.Y)


def income_in(doc: YearDocument, accounts: Collection[str], months: Sequence[Month]) -> Decimal:
    """Marked income (UAH, NBU rate on the receipt date) of `accounts` in `months`."""
    wanted = set(months)
    total = ZERO
    for mark in doc.marks.values():
        payment = doc.payments[mark.payment_id]
        if payment.account_id in accounts and month_of(payment.tax_date) in wanted:
            total += income_uah(payment, mark, doc.rates)
    return total


def require_reviewed(doc: YearDocument, accounts: Collection[str], months: Sequence[Month]) -> None:
    """Marked income is only trustworthy once the user confirmed each account-month as done.
    An unconfirmed month would silently count as zero income, so it is an error instead."""
    missing = {
        f"{month.year}-{month.month:02d}"
        for account in accounts
        for month in months
        if state_of(doc, account, month) is not MonthState.REVIEWED
    }
    if missing:
        raise MonthsNotReviewedError(months=", ".join(sorted(missing)))


def typed_previous(doc: YearDocument, period: Period) -> PreviousDeclaration | None:
    """The latest value the user typed from a filed declaration of `period` (MANUAL wins)."""
    manual = [d for d in doc.declarations if d.period is period and d.source is MarkSource.MANUAL]
    if not manual:
        return None
    last = max(manual, key=lambda d: d.entered_at)
    return PreviousDeclaration(
        last.period, last.income, last.row_07_income_15, last.row_12_tax, last.row_23_levy
    )


def compute_previous(
    doc: YearDocument, up_to: Period, accounts: Collection[str], year: int, rules: Rules
) -> PreviousDeclaration:
    """Path B: chain Q1 -> ... -> `up_to` from marked income (every quarter must be fetched)."""
    require_reviewed(doc, accounts, months_between(Month(year, 1), last_month(up_to, year)))
    previous: PreviousDeclaration | None = None
    for period in PERIOD_CHAIN[: PERIOD_CHAIN.index(up_to) + 1]:
        new_income = income_in(doc, accounts, increment_months(period, year))
        rows = build_declaration(period, year, new_income, previous, rules)
        previous = PreviousDeclaration(period, rows.income, ZERO, rows.row_12, rows.row_23)
    if previous is None:  # unreachable: the chain slice always has at least Q1
        raise ValueError(f"empty period chain for {up_to}")
    return previous


class ReportService:
    def __init__(self, store: YearStore, clock: Clock) -> None:
        self._store = store
        self._clock = clock

    def months_estimate(
        self, selection: MonthsSelection, accounts: Collection[str], rules: Rules
    ) -> Estimate:
        doc = self._store.load(selection.year)
        require_reviewed(doc, accounts, selection.months)
        income = income_in(doc, accounts, selection.months)
        return estimate(income, len(selection.months), rules)

    def save_typed_previous(self, year: int, previous: PreviousDeclaration, rules: Rules) -> None:
        """Validate the rows typed from the cabinet, then store them (MANUAL, timestamped)."""
        validate_previous_rows(previous, rules)
        doc = self._store.load(year)
        doc.declarations.append(_as_input(previous, MarkSource.MANUAL, self._clock.now()))
        self._store.save(doc)

    def declaration(
        self,
        year: int,
        period: Period,
        accounts: Collection[str],
        previous: PreviousDeclaration | None,
        rules: Rules,
    ) -> DeclarationRows:
        doc = self._store.load(year)
        months = increment_months(period, year)
        require_reviewed(doc, accounts, months)
        new_income = income_in(doc, accounts, months)
        return build_declaration(period, year, new_income, previous, rules)

    def previous_for(
        self, year: int, period: Period, accounts: Collection[str], rules: Rules
    ) -> PreviousDeclaration | None:
        """Stored MANUAL value if any, else Path B computed from bank data (None for Q1)."""
        before = previous_period(period)
        if before is None:
            return None
        doc = self._store.load(year)
        return typed_previous(doc, before) or compute_previous(doc, before, accounts, year, rules)


def _as_input(prev: PreviousDeclaration, source: MarkSource, at: datetime) -> DeclarationInput:
    return DeclarationInput(
        period=prev.period,
        income=prev.income,
        row_07_income_15=prev.row_07_income_15,
        row_12_tax=prev.row_12_tax,
        row_23_levy=prev.row_23_levy,
        source=source,
        entered_at=at,
    )
