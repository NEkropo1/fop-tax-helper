"""Exact arithmetic for the cumulative F0103309 declaration (ФОП group 3).

The declaration is cumulative: a 9-month report holds income of Q1+Q2+Q3. Rows that depend on
earlier reports (13, 24) are copied from rows 12 and 23 of the preceding declaration. Row numbers
and rates come from the rules file; the formulas below (two secondary sources agree, and the live
form in the cabinet confirms the surrounding rows):

    income row (06 at 5%, 05 at 3%)   cumulative income         (entered by the payer)
    08   total income                  = income (+ 07, unsupported)
    tax row (11 at 5%, 10 at 3%)      = income x rate
    12   total single tax             = tax row
    13   previous period's tax        = previous row 12 (empty in Q1)
    14   single tax payable now       = 12 - 13   (14.2, the agricultural MPZ, does not apply)
    23   military levy for the period = income x levy rate
    24   previous period's levy       = previous row 23 (empty in Q1)
    25   military levy payable now    = 23 - 24

Anything outside this scope raises an AppError instead of producing a plausible wrong number.
"""

from dataclasses import dataclass
from decimal import Decimal

from mono_it_tax.config.enums import Period
from mono_it_tax.config.rules import Rules
from mono_it_tax.domain.money import round_money
from mono_it_tax.domain.periods import previous_period
from mono_it_tax.errors import (
    DeclIncomeOverLimitError,
    DeclNegativeError,
    DeclPreviousForbiddenError,
    DeclPreviousNotAdjacentError,
    DeclPreviousRequiredError,
    DeclRow07NotZeroError,
    DeclRowMismatchError,
    DeclRulesYearError,
)

ZERO = Decimal(0)


@dataclass(frozen=True)
class PreviousDeclaration:
    """Rows of the previous filed declaration (typed from the e-cabinet, or computed)."""

    period: Period
    income: Decimal  # the regime's income row (06 at 5%, 05 at 3%)
    row_07_income_15: Decimal  # must be 0: the 15% regime is out of scope
    row_12_tax: Decimal
    row_23_levy: Decimal


@dataclass(frozen=True)
class DeclarationRows:
    period: Period
    year: int
    new_income: Decimal  # income of the quarter this period adds (input, for the texts)
    income: Decimal  # regime income row, and row 08
    tax_at_rate: Decimal  # regime tax row
    row_12: Decimal
    row_13: Decimal
    row_14: Decimal
    row_23: Decimal
    row_24: Decimal
    row_25: Decimal


def validate_previous_rows(prev: PreviousDeclaration, rules: Rules) -> None:
    """Typed or computed rows must agree: row 07 zero, no negatives, rows 12/23 = income x rate."""
    rows = rules.declaration.rows
    if prev.row_07_income_15 != ZERO:
        raise DeclRow07NotZeroError(row=rows.income_15)
    for row, value in (
        (rules.single_tax.income_row, prev.income),
        (rows.tax_total, prev.row_12_tax),
        (rows.levy_total, prev.row_23_levy),
    ):
        if value < ZERO:
            raise DeclNegativeError(what=row)
    want_tax = round_money(prev.income * rules.single_tax.rate)
    want_levy = round_money(prev.income * rules.military_levy_rate)
    if prev.row_12_tax != want_tax:
        raise DeclRowMismatchError(row=rows.tax_total, typed=prev.row_12_tax, expected=want_tax)
    if prev.row_23_levy != want_levy:
        raise DeclRowMismatchError(row=rows.levy_total, typed=prev.row_23_levy, expected=want_levy)


def _check_previous(prev: PreviousDeclaration, expected: Period | None, rules: Rules) -> None:
    if expected is None:
        raise DeclPreviousForbiddenError(period=Period.Q1.value)
    if prev.period is not expected:
        raise DeclPreviousNotAdjacentError(expected=expected.value, got=prev.period.value)
    validate_previous_rows(prev, rules)


def build_declaration(
    period: Period,
    year: int,
    new_income_uah: Decimal,
    previous: PreviousDeclaration | None,
    rules: Rules,
) -> DeclarationRows:
    """Rows of the `period` declaration.

    `new_income_uah` is income received ONLY in the quarter this period adds (e.g. Jul-Sep for M9).
    """
    if rules.year != year:
        raise DeclRulesYearError(rules_year=rules.year, year=year)
    if new_income_uah < ZERO:
        raise DeclNegativeError(what=rules.single_tax.income_row)
    expected = previous_period(period)
    if expected is not None and previous is None:
        raise DeclPreviousRequiredError(period=period.value, previous=expected.value)
    if previous is not None:
        _check_previous(previous, expected, rules)

    income = round_money((previous.income if previous else ZERO) + new_income_uah)
    if income > rules.income_limit_uah:
        raise DeclIncomeOverLimitError(income=income, limit=rules.income_limit_uah)

    tax = round_money(income * rules.single_tax.rate)
    levy = round_money(income * rules.military_levy_rate)
    row_13 = previous.row_12_tax if previous else ZERO
    row_24 = previous.row_23_levy if previous else ZERO
    return DeclarationRows(
        period=period,
        year=year,
        new_income=round_money(new_income_uah),
        income=income,
        tax_at_rate=tax,
        row_12=tax,
        row_13=row_13,
        row_14=tax - row_13,
        row_23=levy,
        row_24=row_24,
        row_25=levy - row_24,
    )
