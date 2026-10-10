"""Pipeline: selection -> what has to be fetched -> fetch -> rates for marked foreign income."""

from collections.abc import Callable, Sequence

from mono_it_tax.domain.months import Month
from mono_it_tax.domain.periods import MonthsSelection, PeriodSelection, Selection, history_months
from mono_it_tax.services.fetch import FetchOutcome, FetchPlan, FetchProgress, FetchService
from mono_it_tax.store.year_store import YearStore


def months_to_fetch(selection: Selection, *, with_history: bool = False) -> tuple[Month, ...]:
    """A tax period fetches only the quarter it adds; earlier ones only for Path B (computed)."""
    if isinstance(selection, MonthsSelection):
        return selection.months
    if isinstance(selection, PeriodSelection) and with_history:
        return (*history_months(selection.period, selection.year), *selection.months)
    return selection.months


class FetchPipeline:
    def __init__(self, fetch: FetchService, store: YearStore) -> None:
        self._fetch = fetch
        self._store = store

    def prepare(
        self, selection: Selection, account_ids: Sequence[str], *, with_history: bool = False
    ) -> FetchPlan:
        doc = self._store.load(selection.year)
        return self._fetch.plan(
            doc, account_ids, months_to_fetch(selection, with_history=with_history)
        )

    def execute(
        self,
        selection: Selection,
        plan: FetchPlan,
        on_progress: Callable[[FetchProgress], None] | None = None,
        should_cancel: Callable[[], bool] | None = None,
    ) -> FetchOutcome:
        return self._fetch.run(selection.year, plan, on_progress, should_cancel)
