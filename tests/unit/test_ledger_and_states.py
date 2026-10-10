from datetime import UTC, datetime, timedelta
from itertools import pairwise

from hypothesis import given
from hypothesis import strategies as st

from mono_it_tax.config.enums import Coverage, MonthState, Scope
from mono_it_tax.domain.ledger import FetchRecord, coverage, covered_intervals, missing_ranges
from mono_it_tax.domain.months import Month
from mono_it_tax.domain.states import Review, can_transition, month_state

ACC = "acc-1"
APRIL = Month(2026, 4)
NOW = datetime(2026, 10, 10, tzinfo=UTC)


def record(start: datetime, end: datetime, account: str = ACC, kept: int = 0) -> FetchRecord:
    return FetchRecord(
        account_id=account,
        requested_from=start,
        requested_to=end,
        fetched_at=NOW,
        items_received=kept,
        items_kept=kept,
    )


def full(month: Month, account: str = ACC) -> FetchRecord:
    return record(month.start_utc, month.end_utc, account)


def test_empty_ledger_means_nothing_fetched() -> None:
    assert coverage([], ACC, APRIL) is Coverage.NONE
    assert missing_ranges([], ACC, APRIL) == ((APRIL.start_utc, APRIL.end_utc),)


def test_an_answered_empty_month_is_full_coverage() -> None:
    ledger = [full(APRIL)]  # zero items kept: the request is the truth, not the payments
    assert coverage(ledger, ACC, APRIL) is Coverage.FULL
    assert missing_ranges(ledger, ACC, APRIL) == ()


def test_partial_month_requests_only_the_gap() -> None:
    mid = APRIL.start_utc + timedelta(days=10)
    ledger = [record(APRIL.start_utc, mid)]
    assert coverage(ledger, ACC, APRIL) is Coverage.PARTIAL
    assert missing_ranges(ledger, ACC, APRIL) == ((mid, APRIL.end_utc),)


def test_gap_in_the_middle_is_found() -> None:
    a = APRIL.start_utc + timedelta(days=5)
    b = APRIL.start_utc + timedelta(days=9)
    ledger = [record(APRIL.start_utc, a), record(b, APRIL.end_utc)]
    assert missing_ranges(ledger, ACC, APRIL) == ((a, b),)


def test_other_account_or_scope_does_not_count() -> None:
    assert coverage([full(APRIL, "other")], ACC, APRIL) is Coverage.NONE
    assert covered_intervals([full(APRIL)], ACC, scope=Scope.INCOMING_ONLY) != []


def test_unfinished_month_is_partial_until_it_ends() -> None:
    today = APRIL.start_utc + timedelta(days=12)
    ledger = [record(APRIL.start_utc, today)]  # fetched "up to now" while the month still runs
    assert coverage(ledger, ACC, APRIL) is Coverage.PARTIAL


def test_neighbour_month_request_overlap_does_not_hide_a_gap() -> None:
    march = Month(2026, 3)
    ledger = [record(march.start_utc, APRIL.start_utc + timedelta(seconds=1))]
    assert coverage(ledger, ACC, march) is Coverage.FULL
    assert coverage(ledger, ACC, APRIL) is Coverage.PARTIAL


@given(st.lists(st.tuples(st.integers(0, 30 * 24), st.integers(1, 30 * 24)), max_size=6))
def test_gaps_and_covered_ranges_tile_the_month_exactly(spans: list[tuple[int, int]]) -> None:
    ledger = [
        record(APRIL.start_utc + timedelta(hours=s), APRIL.start_utc + timedelta(hours=s + length))
        for s, length in spans
    ]
    gaps = missing_ranges(ledger, ACC, APRIL)
    covered = [
        (max(a, APRIL.start_utc), min(b, APRIL.end_utc))
        for a, b in covered_intervals(ledger, ACC)
        if a < APRIL.end_utc and b > APRIL.start_utc
    ]
    pieces = sorted([*gaps, *covered])
    assert sum((b - a for a, b in pieces), timedelta()) == APRIL.end_utc - APRIL.start_utc
    for (_, end), (start, _) in pairwise(pieces):
        assert end == start  # no overlap, no hole


def review(ids: tuple[str, ...]) -> Review:
    return Review(account_id=ACC, year=2026, month=4, payment_ids=ids, reviewed_at=NOW)


def test_month_state_lifecycle() -> None:
    ids = frozenset({"a", "b"})
    assert month_state([], None, frozenset(), ACC, APRIL) is MonthState.NOT_FETCHED
    half = [record(APRIL.start_utc, APRIL.start_utc + timedelta(days=3))]
    assert month_state(half, None, ids, ACC, APRIL) is MonthState.PARTIAL
    assert month_state([full(APRIL)], None, ids, ACC, APRIL) is MonthState.FETCHED
    assert month_state([full(APRIL)], review(("a", "b")), ids, ACC, APRIL) is MonthState.REVIEWED


def test_review_with_zero_marks_is_still_reviewed() -> None:
    assert month_state([full(APRIL)], review(()), frozenset(), ACC, APRIL) is MonthState.REVIEWED


def test_new_payment_ids_demote_a_reviewed_month() -> None:
    state = month_state([full(APRIL)], review(("a",)), frozenset({"a", "new"}), ACC, APRIL)
    assert state is MonthState.FETCHED


def test_transition_table() -> None:
    assert can_transition(MonthState.FETCHED, MonthState.REVIEWED)
    assert can_transition(MonthState.REVIEWED, MonthState.FETCHED)
    assert not can_transition(MonthState.NOT_FETCHED, MonthState.REVIEWED)
    assert not can_transition(MonthState.PARTIAL, MonthState.REVIEWED)
