"""Request/response models of the local API. Account ids never appear here, only opaque handles."""

import re
from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from mono_it_tax.api.jobs import JobState
from mono_it_tax.config.enums import ErrorCode, MonthState, Period
from mono_it_tax.domain.months import Month
from mono_it_tax.domain.periods import MonthsSelection, PeriodSelection, Selection

MONTH_PATTERN = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def parse_month(text: str) -> Month:
    match = MONTH_PATTERN.fullmatch(text)
    if match is None:
        raise ValueError(f"month must look like 2026-07, got {text!r}")
    return Month(int(match[1]), int(match[2]))


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SelectionIn(_Request):
    """Either a tax period of a year, or any months of one year."""

    year: int
    kind: Literal["period", "months"]
    period: Period | None = None
    months: list[str] = []

    @field_validator("months")
    @classmethod
    def _valid_months(cls, v: list[str]) -> list[str]:
        for item in v:
            parse_month(item)
        return v

    @model_validator(mode="after")
    def _period_is_present(self) -> "SelectionIn":
        if self.kind == "period" and self.period is None:
            raise ValueError("period is required when kind = 'period'")
        return self

    def to_domain(self) -> Selection:
        if self.kind == "period" and self.period is not None:
            return PeriodSelection(self.year, self.period)
        return MonthsSelection(tuple(parse_month(m) for m in self.months))


class ScopeIn(_Request):
    """What the user works on: a selection, the chosen accounts (handles), and fetch depth."""

    selection: SelectionIn
    handles: list[str]
    with_history: bool = False


class MarkIn(_Request):
    year: int
    payment_ids: list[str]
    marked: bool


class AmountIn(_Request):
    year: int
    payment_id: str
    amount: str | None = None  # major units in the payment's currency; null removes the correction


class ReviewIn(_Request):
    year: int
    handles: list[str]
    months: list[str]


class PreviousIn(_Request):
    """Rows of the previous filed declaration, as typed from the cabinet."""

    income: str
    row_07: str
    row_12: str
    row_23: str


class DeclarationIn(_Request):
    year: int
    period: Period
    handles: list[str]
    previous: PreviousIn | None = None


class ErrorOut(BaseModel):
    code: ErrorCode | Literal["internal"]
    message: str
    params: dict[str, str] = {}


class AccountOut(BaseModel):
    handle: str
    type: str | None
    currency: str
    masked_pans: list[str]  # every card of the account, masked; empty for a ФОП account
    selectable: bool  # false when the account currency is not supported yet


class PlanTaskOut(BaseModel):
    handle: str
    month: str


class PlanOut(BaseModel):
    requests: int
    eta_seconds: float
    tasks: list[PlanTaskOut]


class JobOut(BaseModel):
    id: str
    state: JobState
    done: int
    total: int
    month: str | None
    error: ErrorOut | None


class PaymentOut(BaseModel):
    id: str
    handle: str
    month: str
    time: str  # Kyiv local time, ISO
    amount: str  # in the account currency
    currency: str  # the account currency
    operation_currency: str | None  # original operation currency (differs on a conversion)
    description: str | None
    comment: str | None
    counter_name: str | None
    counter_edrpou: str | None
    counter_iban: str | None
    mcc: int | None
    original_mcc: int | None
    operation_amount: str | None
    commission_rate: str | None
    cashback_amount: str | None
    balance: str | None
    hold: bool | None
    extra: dict[str, Any]
    possible_internal_transfer: bool
    marked: bool
    amount_override: str | None


class MonthStateOut(BaseModel):
    handle: str
    month: str
    state: MonthState
    payments: int
    marked: int


class PaymentsOut(BaseModel):
    payments: list[PaymentOut]
    months: list[MonthStateOut]


class RateEstimateOut(BaseModel):
    rate: str  # fraction, e.g. "0.05"
    single_tax: str
    total: str


class EstimateOut(BaseModel):
    income: str
    military_levy: str
    esv: str
    by_rate: list[RateEstimateOut]
    months: int
    text: str


class PlannedPaymentOut(BaseModel):
    tax: str
    amount: str
    due: date
    budget_code: str


class DeclarationOut(BaseModel):
    text: str
    preliminary: bool
    declaration_due: date
    payments: list[PlannedPaymentOut]
    rows: dict[str, str]


class RulesOut(BaseModel):
    year: int
    version: str
    updated_on: date
    disclaimer: str
    cabinet: str
    tax_account: str
    new_declaration: str
    declaration_video: str
    channels: list[dict[str, str]]
    linkedin: str


class MetaOut(BaseModel):
    ready: bool
    error: ErrorOut | None
    version: str
    store_key: str | None
    years: list[int]  # years that have a rules file
    current_year: int | None  # today's year in Kyiv time
    rules: RulesOut | None


class DataYearOut(BaseModel):
    year: int
    bytes: int


class DataOut(BaseModel):
    folder: str
    years: list[DataYearOut]
    key_storage: str | None
