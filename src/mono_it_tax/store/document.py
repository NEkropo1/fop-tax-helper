"""The per-year document kept in the encrypted store."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from mono_it_tax.config.constants.store import STORE_SCHEMA_VERSION
from mono_it_tax.config.enums import Currency, MarkSource, Period
from mono_it_tax.domain.account import Account
from mono_it_tax.domain.income import Mark
from mono_it_tax.domain.ledger import FetchRecord
from mono_it_tax.domain.payment import Payment
from mono_it_tax.domain.states import Review


class DeclarationInput(BaseModel):
    """Rows of a declaration of this year, with where they came from. A MANUAL value (what was
    actually filed) wins over a COMPUTED one."""

    model_config = ConfigDict(frozen=True)

    period: Period
    income: Decimal
    row_07_income_15: Decimal
    row_12_tax: Decimal
    row_23_levy: Decimal
    source: MarkSource
    entered_at: datetime


class YearDocument(BaseModel):
    """Everything fetched and decided for one tax year. Append-only data, never auto-deleted."""

    schema_version: int = STORE_SCHEMA_VERSION
    year: int
    accounts: tuple[Account, ...] = ()
    tax_accounts: tuple[str, ...] = ()  # account ids used for this tax year
    ledger: list[FetchRecord] = Field(default_factory=list)
    payments: dict[str, Payment] = Field(default_factory=dict)
    marks: dict[str, Mark] = Field(default_factory=dict)
    reviews: list[Review] = Field(default_factory=list)
    rates: dict[Currency, dict[date, Decimal]] = Field(default_factory=dict)
    declarations: list[DeclarationInput] = Field(default_factory=list)
