from datetime import UTC, date, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mono_it_tax.config.constants.api import MONOBANK_MAX_SPAN_S
from mono_it_tax.config.enums import Period
from mono_it_tax.domain.months import Month, kyiv_date, month_of, months_between
from mono_it_tax.domain.periods import (
    MonthsSelection,
    PeriodSelection,
    history_months,
    increment_months,
    period_end,
    previous_period,
)
from mono_it_tax.errors import SelectionEmptyError, SelectionMultiYearError


def test_month_rejects_invalid_number() -> None:
    with pytest.raises(ValueError, match="month must be"):
        Month(2026, 13)


def test_month_prints_as_year_dash_month() -> None:
    assert str(Month(2026, 7)) == "2026-07"


def test_month_next_wraps_the_year() -> None:
    assert Month(2026, 12).next() == Month(2027, 1)
    assert Month(2026, 3).next() == Month(2026, 4)


def test_kyiv_month_bounds_are_utc_instants() -> None:
    # April 2026: DST already in force (UTC+3) -> Kyiv midnight is 21:00 UTC the day before
    assert Month(2026, 4).start_utc == datetime(2026, 3, 31, 21, 0, tzinfo=UTC)
    # January: UTC+2
    assert Month(2026, 1).start_utc == datetime(2025, 12, 31, 22, 0, tzinfo=UTC)


def test_kyiv_date_differs_from_utc_date_around_midnight() -> None:
    instant = datetime(2026, 3, 31, 21, 30, tzinfo=UTC)  # 00:30 on 1 April in Kyiv
    assert instant.date() == date(2026, 3, 31)
    assert kyiv_date(instant) == date(2026, 4, 1)
    assert month_of(kyiv_date(instant)) == Month(2026, 4)


def test_year_boundary_in_kyiv_vs_utc() -> None:
    instant = datetime(2026, 12, 31, 22, 30, tzinfo=UTC)  # 00:30 on 1 January 2027 in Kyiv
    assert kyiv_date(instant) == date(2027, 1, 1)


@pytest.mark.parametrize(
    ("month", "span_hours"),
    [
        (Month(2026, 3), 31 * 24 - 1),  # spring DST month is an hour shorter
        (Month(2026, 10), 31 * 24 + 1),  # autumn DST month is an hour longer
        (Month(2026, 2), 28 * 24),
    ],
)
def test_dst_months_have_real_length(month: Month, span_hours: int) -> None:
    delta = month.end_utc - month.start_utc
    assert delta.total_seconds() == span_hours * 3600


def test_every_month_fits_one_api_request() -> None:
    """The longest Kyiv month (October after DST) is exactly the API maximum: one request each."""
    for year in range(2024, 2031):
        for number in range(1, 13):
            month = Month(year, number)
            assert (month.end_utc - month.start_utc).total_seconds() <= MONOBANK_MAX_SPAN_S


@given(st.integers(min_value=2000, max_value=2100), st.integers(min_value=1, max_value=12))
def test_consecutive_months_tile_without_gaps(year: int, number: int) -> None:
    month = Month(year, number)
    assert month.end_utc == month.next().start_utc


def test_months_between_inclusive_and_empty() -> None:
    assert months_between(Month(2026, 11), Month(2027, 1)) == (
        Month(2026, 11),
        Month(2026, 12),
        Month(2027, 1),
    )
    assert months_between(Month(2026, 5), Month(2026, 4)) == ()


@pytest.mark.parametrize(
    ("period", "expected_months"),
    [
        (Period.Q1, (1, 2, 3)),
        (Period.H1, (4, 5, 6)),
        (Period.M9, (7, 8, 9)),
        (Period.Y, (10, 11, 12)),
    ],
)
def test_period_adds_exactly_one_quarter(period: Period, expected_months: tuple[int, ...]) -> None:
    assert tuple(m.month for m in increment_months(period, 2026)) == expected_months
    assert PeriodSelection(2026, period).months == increment_months(period, 2026)


def test_period_chain_and_ends() -> None:
    assert previous_period(Period.Q1) is None
    assert previous_period(Period.Y) is Period.M9
    assert period_end(Period.Q1, 2026) == date(2026, 3, 31)
    assert period_end(Period.H1, 2026) == date(2026, 6, 30)
    assert period_end(Period.M9, 2026) == date(2026, 9, 30)
    assert period_end(Period.Y, 2026) == date(2026, 12, 31)


def test_history_is_everything_before_the_increment() -> None:
    assert history_months(Period.Q1, 2026) == ()
    assert [m.month for m in history_months(Period.M9, 2026)] == [1, 2, 3, 4, 5, 6]
    assert [m.month for m in history_months(Period.Y, 2026)] == list(range(1, 10))


def test_months_selection_validates() -> None:
    with pytest.raises(SelectionEmptyError):
        MonthsSelection(())
    with pytest.raises(SelectionMultiYearError):
        MonthsSelection((Month(2025, 12), Month(2026, 1)))
    assert MonthsSelection((Month(2026, 2), Month(2026, 7))).year == 2026
