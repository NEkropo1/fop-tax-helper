"""Tax reporting periods and what the user can select."""

from dataclasses import dataclass
from datetime import date, timedelta

from mono_it_tax.config.constants.tax import PERIOD_LAST_QUARTER, PERIOD_PREVIOUS
from mono_it_tax.config.constants.time import MONTHS_IN_QUARTER
from mono_it_tax.config.enums import Period
from mono_it_tax.domain.months import Month, months_between
from mono_it_tax.errors import SelectionEmptyError, SelectionMultiYearError


def previous_period(period: Period) -> Period | None:
    return PERIOD_PREVIOUS[period]


def last_month(period: Period, year: int) -> Month:
    return Month(year, PERIOD_LAST_QUARTER[period] * MONTHS_IN_QUARTER)


def period_end(period: Period, year: int) -> date:
    """Last calendar day of the period."""
    return last_month(period, year).next().first_day - timedelta(days=1)


def increment_months(period: Period, year: int) -> tuple[Month, ...]:
    """The months of the single quarter this period adds on top of the previous one."""
    last = last_month(period, year)
    return months_between(Month(year, last.month - MONTHS_IN_QUARTER + 1), last)


def history_months(period: Period, year: int) -> tuple[Month, ...]:
    """All months from January up to the end of the period before `period` (empty for Q1)."""
    prev = previous_period(period)
    if prev is None:
        return ()
    return months_between(Month(year, 1), last_month(prev, year))


@dataclass(frozen=True)
class PeriodSelection:
    """A tax period: fetch only the quarter it adds; history only when declaration help needs it."""

    year: int
    period: Period

    @property
    def months(self) -> tuple[Month, ...]:
        return increment_months(self.period, self.year)

    @property
    def end(self) -> date:
        return period_end(self.period, self.year)


@dataclass(frozen=True)
class MonthsSelection:
    """Any months of one calendar year; indicative numbers only, no declaration help."""

    months: tuple[Month, ...]

    def __post_init__(self) -> None:
        if not self.months:
            raise SelectionEmptyError
        if len({m.year for m in self.months}) > 1:
            raise SelectionMultiYearError

    @property
    def year(self) -> int:
        return self.months[0].year


Selection = PeriodSelection | MonthsSelection
