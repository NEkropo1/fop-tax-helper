"""Calendar months in Europe/Kyiv: the unit of fetching, coverage and tax dates."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from mono_it_tax.config.constants.time import KYIV_TZ_NAME, MONTHS_IN_YEAR

KYIV = ZoneInfo(KYIV_TZ_NAME)


@dataclass(frozen=True, order=True)
class Month:
    year: int
    month: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= MONTHS_IN_YEAR:
            raise ValueError(f"month must be 1..{MONTHS_IN_YEAR}, got {self.month}")

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"

    def next(self) -> "Month":
        if self.month == MONTHS_IN_YEAR:
            return Month(self.year + 1, 1)
        return Month(self.year, self.month + 1)

    @property
    def first_day(self) -> date:
        return date(self.year, self.month, 1)

    @property
    def start_utc(self) -> datetime:
        """Kyiv midnight of the first day, as a UTC instant."""
        return datetime(self.year, self.month, 1, tzinfo=KYIV).astimezone(UTC)

    @property
    def end_utc(self) -> datetime:
        """Kyiv midnight of the next month's first day (exclusive end), as a UTC instant."""
        return self.next().start_utc


def month_of(day: date) -> Month:
    return Month(day.year, day.month)


def kyiv_date(instant: datetime) -> date:
    """Kyiv calendar day of an instant (01:00 on 1 April in Kyiv is still 31 March in UTC)."""
    return instant.astimezone(KYIV).date()


def months_between(first: Month, last: Month) -> tuple[Month, ...]:
    """Inclusive range of months; empty if `last` is before `first`."""
    out: list[Month] = []
    current = first
    while current <= last:
        out.append(current)
        current = current.next()
    return tuple(out)
