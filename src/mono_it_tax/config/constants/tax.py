"""Structure of the cumulative reporting periods (rates live in data/rules/<year>.yaml)."""

from mono_it_tax.config.enums import Period

PERIOD_LAST_QUARTER: dict[Period, int] = {Period.Q1: 1, Period.H1: 2, Period.M9: 3, Period.Y: 4}
PERIOD_PREVIOUS: dict[Period, Period | None] = {
    Period.Q1: None,
    Period.H1: Period.Q1,
    Period.M9: Period.H1,
    Period.Y: Period.M9,
}
