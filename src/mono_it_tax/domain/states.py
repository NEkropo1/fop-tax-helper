"""Per (account, month) lifecycle, derived from the ledger and the user's reviews (never stored).

NOT_FETCHED -> PARTIAL -> FETCHED -> REVIEWED, and REVIEWED falls back to FETCHED when a refetch
brings payment ids the user has not seen yet.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from mono_it_tax.config.enums import Coverage, MonthState
from mono_it_tax.domain.ledger import FetchRecord, coverage
from mono_it_tax.domain.months import Month


class Review(BaseModel):
    """'Income marked, done' for one account-month, with the payment ids the user saw."""

    model_config = ConfigDict(frozen=True)

    account_id: str
    year: int
    month: int
    payment_ids: tuple[str, ...]
    reviewed_at: datetime


ALLOWED_TRANSITIONS: dict[MonthState, frozenset[MonthState]] = {
    MonthState.NOT_FETCHED: frozenset(
        {MonthState.NOT_FETCHED, MonthState.PARTIAL, MonthState.FETCHED}
    ),
    MonthState.PARTIAL: frozenset({MonthState.PARTIAL, MonthState.FETCHED}),
    MonthState.FETCHED: frozenset({MonthState.FETCHED, MonthState.REVIEWED}),
    MonthState.REVIEWED: frozenset({MonthState.REVIEWED, MonthState.FETCHED}),
}


def month_state(
    ledger: tuple[FetchRecord, ...] | list[FetchRecord],
    review: Review | None,
    payment_ids: frozenset[str],
    account_id: str,
    month: Month,
) -> MonthState:
    cov = coverage(ledger, account_id, month)
    if cov is Coverage.NONE:
        return MonthState.NOT_FETCHED
    if cov is Coverage.PARTIAL:
        return MonthState.PARTIAL
    if review is not None and payment_ids <= set(review.payment_ids):
        return MonthState.REVIEWED
    return MonthState.FETCHED


def can_transition(old: MonthState, new: MonthState) -> bool:
    return new in ALLOWED_TRANSITIONS[old]
