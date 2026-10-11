"""Yearly tax rules: data with a source, loaded and validated once. A bad file fails at startup."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from mono_it_tax.config.constants.time import MONTHS_IN_QUARTER
from mono_it_tax.config.enums import Tax
from mono_it_tax.errors import ConfigRulesInvalidError, ConfigRulesMissingError


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Regime(_Frozen):
    """Single-tax regime: rate and the declaration rows it uses (5% -> 06/11, 3% -> 05/10)."""

    rate: Decimal
    income_row: str
    tax_row: str
    note: str  # who this regime is for, shown next to the row number


class DeclarationRows(_Frozen):
    """Row numbers of form F0103309 that the app reads or tells the user to check."""

    income_15: str
    total_income: str
    tax_total: str
    tax_previous: str
    tax_due_base: str
    tax_due_extra: str
    tax_due: str
    esv_due: str
    levy_total: str
    levy_previous: str
    levy_due: str


class DeclarationFields(_Frozen):
    """Numbered fields (not rows) of the form that the user checks or fills before the rows."""

    office: str
    taxpayer: str
    employees: str


class Declaration(_Frozen):
    form: str
    order: str
    fields: DeclarationFields
    rows: DeclarationRows
    empty_rows: tuple[str, ...]


class Deadlines(_Frozen):
    declaration_days_after_quarter_end: int
    single_tax_days_after_quarter_end: int
    esv_day_of_next_month: int


class Links(_Frozen):
    cabinet: str
    tax_account: str
    new_declaration: str
    requisites_xlsx: str
    legislation: str  # the Tax Code: the binding source for every figure
    tax_service: str  # the tax service site (official explanations, forms)
    declaration_video: str | None = None  # optional third-party walkthrough; omitted by default


class RecommendedSource(_Frozen):
    """Optional third-party material (channel, blog). Listed only with its owner's consent."""

    name: str
    url: str


class Contact(_Frozen):
    linkedin: str


class InternalTransferRule(_Frozen):
    """Hint only: a payment that looks like a move between the user's own cards."""

    mcc: int
    description_prefixes: tuple[str, ...]


class Rules(_Frozen):
    version: str
    updated_on: date
    year: int
    group: int
    minimum_wage_uah: Decimal
    esv_rate: Decimal
    single_tax: Regime
    estimate_rates: tuple[
        Decimal, ...
    ]  # single-tax rates the indicative estimate shows side by side
    military_levy_rate: Decimal
    income_limit_uah: Decimal
    sources: tuple[str, ...]
    deadlines: Deadlines
    declaration: Declaration
    budget_codes: dict[Tax, str]
    links: Links
    recommended_sources: tuple[RecommendedSource, ...] = ()
    contact: Contact
    internal_transfer: InternalTransferRule
    disclaimer: str

    @field_validator("estimate_rates")
    @classmethod
    def _rates_are_fractions(cls, v: tuple[Decimal, ...]) -> tuple[Decimal, ...]:
        if not v or any(not Decimal(0) < rate <= Decimal(1) for rate in v):
            raise ValueError("estimate_rates must be a non-empty list of fractions in (0, 1]")
        return v

    @field_validator("budget_codes")
    @classmethod
    def _all_taxes_have_a_code(cls, v: dict[Tax, str]) -> dict[Tax, str]:
        missing = set(Tax) - set(v)
        if missing:
            raise ValueError(f"budget_codes lacks {sorted(t.value for t in missing)}")
        return v

    @property
    def esv_monthly(self) -> Decimal:
        return self.minimum_wage_uah * self.esv_rate

    @property
    def esv_quarterly(self) -> Decimal:
        return self.esv_monthly * MONTHS_IN_QUARTER


def available_years(rules_dir: Path) -> list[int]:
    """Years that have a rules file (the app can calculate only for these)."""
    if not rules_dir.is_dir():
        return []
    return sorted(int(p.stem) for p in rules_dir.glob("*.yaml") if p.stem.isdigit())


def load_rules(rules_dir: Path, year: int) -> Rules:
    path = rules_dir / f"{year}.yaml"
    if not path.is_file():
        raise ConfigRulesMissingError(path=path)
    try:
        return Rules.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))
    except (yaml.YAMLError, ValidationError) as exc:
        raise ConfigRulesInvalidError(path=path, detail=str(exc).splitlines()[0]) from exc
