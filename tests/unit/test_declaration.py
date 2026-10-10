from dataclasses import replace
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from mono_it_tax.config.enums import Period
from mono_it_tax.config.rules import Regime
from mono_it_tax.domain.declaration import (
    DeclarationRows,
    PreviousDeclaration,
    build_declaration,
    validate_previous_rows,
)
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
from tests.support import make_rules

D = Decimal
RULES = make_rules()
CHAIN = (Period.Q1, Period.H1, Period.M9, Period.Y)


def prev_of(rows: DeclarationRows) -> PreviousDeclaration:
    """What the user would copy from the filed declaration `rows`."""
    return PreviousDeclaration(rows.period, rows.income, D(0), rows.row_12, rows.row_23)


def q1(income: str) -> PreviousDeclaration:
    return prev_of(build_declaration(Period.Q1, 2026, D(income), None, RULES))


def test_q1_with_income() -> None:
    r = build_declaration(Period.Q1, 2026, D("100000"), None, RULES)
    assert r.income == D("100000.00")
    assert r.row_12 == r.row_14 == D("5000.00")
    assert r.row_13 == r.row_24 == D(0)
    assert r.row_23 == r.row_25 == D("1000.00")


def test_q1_without_income_is_all_zero() -> None:
    r = build_declaration(Period.Q1, 2026, D(0), None, RULES)
    assert (r.income, r.row_12, r.row_14, r.row_23, r.row_25) == (D(0),) * 5


def test_zero_income_quarter_after_a_filed_half_year_owes_nothing() -> None:
    h1 = build_declaration(Period.H1, 2026, D("250000.50"), q1("100000"), RULES)
    m9 = build_declaration(Period.M9, 2026, D(0), prev_of(h1), RULES)
    assert m9.income == h1.income
    assert (m9.row_13, m9.row_24) == (h1.row_12, h1.row_23)
    assert (m9.row_14, m9.row_25) == (D(0), D(0))


def test_new_income_pays_only_the_increment() -> None:
    h1 = build_declaration(Period.H1, 2026, D("50000"), q1("100000"), RULES)
    m9 = build_declaration(Period.M9, 2026, D("20000.01"), prev_of(h1), RULES)
    assert m9.income == D("170000.01")
    assert m9.row_12 == D("8500.00")  # 170000.01 * 5% = 8500.0005
    assert m9.row_14 == D("1000.00")  # 8500.00 - 7500.00
    assert m9.row_25 == D("200.00")  # 1700.00 - 1500.00


def test_half_kopiyka_rounds_up() -> None:
    r = build_declaration(Period.Q1, 2026, D("0.10"), None, RULES)  # 0.005 -> 0.01
    assert r.row_12 == D("0.01")
    assert r.row_23 == D("0.00")  # 0.001 -> 0.00


def test_three_percent_regime_uses_the_rows_from_rules() -> None:
    rules = make_rules(single_tax=Regime(rate=D("0.03"), income_row="05", tax_row="10", note="VAT"))
    r = build_declaration(Period.Q1, 2026, D("1000"), None, rules)
    assert r.row_12 == D("30.00")


def test_missing_previous_is_an_error() -> None:
    with pytest.raises(DeclPreviousRequiredError):
        build_declaration(Period.M9, 2026, D(0), None, RULES)


def test_q1_must_not_have_previous() -> None:
    with pytest.raises(DeclPreviousForbiddenError):
        build_declaration(Period.Q1, 2026, D(0), q1("1"), RULES)


def test_previous_must_be_adjacent() -> None:
    with pytest.raises(DeclPreviousNotAdjacentError):
        build_declaration(Period.M9, 2026, D(0), q1("1000"), RULES)


def test_inconsistent_previous_rows_name_the_row() -> None:
    bad_tax = replace(q1("1000"), row_12_tax=D("49.99"))
    with pytest.raises(DeclRowMismatchError) as tax_exc:
        build_declaration(Period.H1, 2026, D(0), bad_tax, RULES)
    assert tax_exc.value.params == {"row": "12", "typed": "49.99", "expected": "50.00"}
    bad_levy = replace(q1("1000"), row_23_levy=D("9.99"))
    with pytest.raises(DeclRowMismatchError) as levy_exc:
        build_declaration(Period.H1, 2026, D(0), bad_levy, RULES)
    assert levy_exc.value.params["row"] == "23"


def test_previous_row_07_rejected() -> None:
    with pytest.raises(DeclRow07NotZeroError):
        validate_previous_rows(replace(q1("1000"), row_07_income_15=D("1")), RULES)


def test_negative_inputs_rejected() -> None:
    with pytest.raises(DeclNegativeError):
        build_declaration(Period.Q1, 2026, D("-1"), None, RULES)
    with pytest.raises(DeclNegativeError):
        validate_previous_rows(replace(q1("0"), income=D("-1")), RULES)


def test_income_over_limit_rejected() -> None:
    with pytest.raises(DeclIncomeOverLimitError):
        build_declaration(Period.Q1, 2026, RULES.income_limit_uah + 1, None, RULES)


def test_income_exactly_at_limit_is_fine() -> None:
    assert build_declaration(Period.Q1, 2026, RULES.income_limit_uah, None, RULES).income == (
        RULES.income_limit_uah
    )


def test_rules_for_another_year_rejected() -> None:
    with pytest.raises(DeclRulesYearError):
        build_declaration(Period.Q1, 2027, D(0), None, RULES)


amounts = st.decimals(min_value=D(0), max_value=D("1000000"), places=2)


@given(st.lists(amounts, min_size=4, max_size=4))
def test_chain_of_periods_equals_one_shot_cumulative(quarters: list[Decimal]) -> None:
    """Q1 -> H1 -> 9m -> Y paid piece by piece equals the cumulative result for the whole year."""
    rows: DeclarationRows | None = None
    paid_tax = paid_levy = D(0)
    for period, chunk in zip(CHAIN, quarters, strict=True):
        rows = build_declaration(period, 2026, chunk, prev_of(rows) if rows else None, RULES)
        paid_tax += rows.row_14
        paid_levy += rows.row_25
    one_shot = build_declaration(Period.Q1, 2026, sum(quarters, D(0)), None, RULES)
    assert rows is not None
    assert rows.income == one_shot.income
    assert (paid_tax, paid_levy) == (one_shot.row_12, one_shot.row_23)
    assert rows.row_14 >= 0
    assert rows.row_25 >= 0


@given(amounts, amounts)
def test_payable_amounts_are_never_negative(first: Decimal, second: Decimal) -> None:
    h1 = build_declaration(Period.H1, 2026, second, q1(str(first)), RULES)
    assert h1.row_14 >= 0
    assert h1.row_25 >= 0
