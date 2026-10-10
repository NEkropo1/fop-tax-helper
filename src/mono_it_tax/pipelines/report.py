"""Pipeline: marked income -> estimate (months) or declaration rows + payments + instructions."""

from collections.abc import Collection
from dataclasses import dataclass

from mono_it_tax.clock import Clock
from mono_it_tax.config.enums import Period
from mono_it_tax.config.rules import Rules
from mono_it_tax.copy.declaration_uk import fill_instructions
from mono_it_tax.copy.estimate_uk import format_estimate
from mono_it_tax.domain.declaration import DeclarationRows, PreviousDeclaration
from mono_it_tax.domain.estimate import Estimate
from mono_it_tax.domain.months import kyiv_date
from mono_it_tax.domain.payment_plan import PaymentPlan, build_plan
from mono_it_tax.domain.periods import MonthsSelection, period_end
from mono_it_tax.services.rates import RatesService
from mono_it_tax.services.reports import ReportService


@dataclass(frozen=True)
class DeclarationHelp:
    rows: DeclarationRows
    plan: PaymentPlan
    text: str
    preliminary: bool  # the period is not over yet: figures will change


class ReportPipeline:
    def __init__(self, reports: ReportService, rates: RatesService, clock: Clock) -> None:
        self._reports = reports
        self._rates = rates
        self._clock = clock

    def months_estimate(
        self, selection: MonthsSelection, accounts: Collection[str], rules: Rules
    ) -> Estimate:
        self._rates.ensure(selection.year)
        return self._reports.months_estimate(selection, accounts, rules)

    def months_report(
        self, selection: MonthsSelection, accounts: Collection[str], rules: Rules
    ) -> str:
        return format_estimate(self.months_estimate(selection, accounts, rules), rules)

    def declaration_help(
        self,
        year: int,
        period: Period,
        accounts: Collection[str],
        rules: Rules,
        typed_previous: PreviousDeclaration | None = None,
    ) -> DeclarationHelp:
        """Path A when `typed_previous` is given (validated, stored as MANUAL); otherwise a stored
        MANUAL value, else Path B computed from the marked income of earlier quarters."""
        if typed_previous is not None:
            self._reports.save_typed_previous(year, typed_previous, rules)
        self._rates.ensure(year)
        previous = typed_previous or self._reports.previous_for(year, period, accounts, rules)
        rows = self._reports.declaration(year, period, accounts, previous, rules)
        plan = build_plan(rows, rules)
        today = kyiv_date(self._clock.now())
        return DeclarationHelp(
            rows=rows,
            plan=plan,
            text=fill_instructions(rows, plan, rules),
            preliminary=period_end(period, year) >= today,
        )
