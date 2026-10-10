"""The fetch ledger: what was REQUESTED and ANSWERED defines what is known, not what exists.

An empty month fetched successfully is full coverage. Coverage is a pure function of ledger records.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from mono_it_tax.config.enums import Coverage, Scope
from mono_it_tax.domain.months import Month

Interval = tuple[datetime, datetime]  # half-open [start, end), UTC


class FetchRecord(BaseModel):
    """One successful, answered request. Append-only. Failed requests are never recorded."""

    model_config = ConfigDict(frozen=True)

    account_id: str
    requested_from: datetime
    requested_to: datetime
    fetched_at: datetime
    items_received: int
    items_kept: int
    scope: Scope = Scope.INCOMING_ONLY


def _merge(intervals: list[Interval]) -> list[Interval]:
    merged: list[Interval] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def covered_intervals(
    ledger: tuple[FetchRecord, ...] | list[FetchRecord],
    account_id: str,
    scope: Scope = Scope.INCOMING_ONLY,
) -> list[Interval]:
    return _merge(
        [
            (r.requested_from, r.requested_to)
            for r in ledger
            if r.account_id == account_id and r.scope == scope
        ]
    )


def missing_ranges(
    ledger: tuple[FetchRecord, ...] | list[FetchRecord],
    account_id: str,
    month: Month,
    scope: Scope = Scope.INCOMING_ONLY,
) -> tuple[Interval, ...]:
    """The parts of the month that no answered request covers (what still has to be requested)."""
    cursor, end = month.start_utc, month.end_utc
    gaps: list[Interval] = []
    for start, stop in covered_intervals(ledger, account_id, scope):
        if stop <= cursor:
            continue
        if start >= end:
            break
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, stop)
    if cursor < end:
        gaps.append((cursor, end))
    return tuple(gaps)


def coverage(
    ledger: tuple[FetchRecord, ...] | list[FetchRecord],
    account_id: str,
    month: Month,
    scope: Scope = Scope.INCOMING_ONLY,
) -> Coverage:
    gaps = missing_ranges(ledger, account_id, month, scope)
    if not gaps:
        return Coverage.FULL
    if gaps == ((month.start_utc, month.end_utc),):
        return Coverage.NONE
    return Coverage.PARTIAL
