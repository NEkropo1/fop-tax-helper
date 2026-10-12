"""The help text must be a faithful rendering of the recorded state: every number from the rows
object, every row number from the rules, wording branches from the state (not hardcoded)."""

from decimal import Decimal

from hypothesis import given
from hypothesis import strategies as st

from mono_it_tax.config.enums import Period
from mono_it_tax.config.rules import DeclarationFields, RecommendedSource, Rules
from mono_it_tax.config.rules import DeclarationRows as RuleRows
from mono_it_tax.copy.declaration_uk import (
    ESV_ROW_NOT_NEEDED,
    PERIOD_LABELS,
    fill_instructions,
    format_money,
)
from mono_it_tax.copy.estimate_uk import format_estimate
from mono_it_tax.domain.declaration import DeclarationRows, PreviousDeclaration, build_declaration
from mono_it_tax.domain.estimate import estimate
from mono_it_tax.domain.payment_plan import build_plan
from tests.support import make_rules

D = Decimal
RULES = make_rules()
H1_FILED = PreviousDeclaration(Period.H1, D("120000.40"), D(0), D("6000.02"), D("1200.00"))


def rows_for(
    period: Period, previous: PreviousDeclaration | None, new_income: str, rules: Rules = RULES
) -> DeclarationRows:
    return build_declaration(period, 2026, D(new_income), previous, rules)


def render(rows: DeclarationRows, rules: Rules = RULES) -> str:
    return fill_instructions(rows, build_plan(rows, rules), rules)


def prev_of(rows: DeclarationRows) -> PreviousDeclaration:
    return PreviousDeclaration(rows.period, rows.income, D(0), rows.row_12, rows.row_23)


def test_nine_months_period_names_both_cabinet_wordings() -> None:
    label = PERIOD_LABELS[Period.M9]
    assert "три квартали" in label
    assert "9 місяців" in label


def test_no_new_income_matches_what_the_cabinet_does() -> None:
    text = render(rows_for(Period.M9, H1_FILED, "0"))
    # 1-3: own data first, then the two rows the cabinet pre-fills, then the employee count
    assert text.index("1. Одразу після створення") < text.index("2. Перевірте підтягнуті")
    assert "у полі 4 — ваша податкова" in text
    assert "рядок 13 = 6 000.02 (це рядок 12 попередньої декларації)" in text
    assert "рядок 24 = 1 200.00 (це рядок 23 попередньої)" in text
    assert "3. У пункті 9 (фактична чисельність найманих працівників)" in text
    # 4: start from row 06 with the cumulative income; no new income -> same as previous
    assert "рядок 06 (розділ IV, ставка 5%" in text
    assert "= 120 000.40 грн" in text
    assert "Нового доходу за липень–вересень немає" in text
    # 5: what appears by itself: 08, 11, 12, 23; zero results stay empty, which equals 0
    for line in (
        "   - 08 (усього доходу) = 120 000.40",
        "   - 11 (податок за ставкою 5%) = 6 000.02",
        "   - 12 (нараховано всього за період) = 6 000.02",
        "   - 23 (військовий збір за період) = 1 200.00",
    ):
        assert line in text
    assert "рядки 14.1 і 14 лишаються порожніми" in text
    assert "рядок 25 лишається порожнім" in text
    assert "   - 14.1 (" not in text
    assert "   - 25 (" not in text


def test_new_income_shows_the_payable_rows_with_their_amounts() -> None:
    rows = rows_for(Period.M9, H1_FILED, "20000.01")
    text = render(rows)
    assert "плюс новий за липень–вересень (20 000.01)" in text
    assert f"= {format_money(rows.row_14)}" in text
    assert "   - 14.1 (до сплати за підсумками періоду, 12 - 13)" in text
    assert "   - 14 (загальна сума єдиного податку до сплати, 14.1 + 14.2)" in text
    assert f"   - 25 (військовий збір до сплати, 23 - 24) = {format_money(rows.row_25)}" in text
    assert "лишаються порожніми: це те саме" not in text


def test_first_period_of_the_year_has_nothing_prefilled() -> None:
    text = render(rows_for(Period.Q1, None, "1000"))
    assert "Це перша декларація року: рядки 13 і 24 мають бути порожні" in text
    assert "Це дохід за січень–березень" in text
    assert "(це рядок 12 попередньої декларації)" not in text


def test_later_period_after_a_zero_quarter_still_expects_prefilled_rows() -> None:
    """Regression: 'first period' is decided by the period, not by zero amounts."""
    q1 = rows_for(Period.Q1, None, "0")
    text = render(rows_for(Period.H1, prev_of(q1), "0"))
    assert "Це перша декларація року" not in text
    assert "Перевірте підтягнуті рядки" in text
    assert "Нового доходу за квітень–червень немає" in text


def test_interim_declarations_say_row_21_and_annex_1_are_not_filled() -> None:
    q1 = rows_for(Period.Q1, None, "0")
    for rows in (q1, rows_for(Period.H1, prev_of(q1), "0")):
        text = render(rows)
        assert ESV_ROW_NOT_NEEDED.format(esv_due="21") in text


def test_annual_declaration_points_to_annex_1_with_the_expected_minimum() -> None:
    rows = rows_for(Period.Q1, None, "0")
    for period in (Period.H1, Period.M9, Period.Y):
        rows = rows_for(period, prev_of(rows), "0")
    text = render(rows)
    assert "Це річна декларація" in text
    assert "22 828.08" in text  # 12 x 1902.34
    assert "лише в річній" not in text


def test_every_row_and_field_number_comes_from_the_rules_not_from_the_text() -> None:
    moved = make_rules(
        declaration={
            **RULES.declaration.model_dump(),
            "fields": DeclarationFields(office="F-OFFICE", taxpayer="F-PAYER", employees="F-STAFF"),
            "rows": RuleRows(
                income_15="R-07",
                total_income="R-08",
                tax_total="R-12",
                tax_previous="R-13",
                tax_due_base="R-141",
                tax_due_extra="R-142",
                tax_due="R-14",
                esv_due="R-21",
                levy_total="R-23",
                levy_previous="R-24",
                levy_due="R-25",
            ),
        },
        single_tax={**RULES.single_tax.model_dump(), "income_row": "R-06", "tax_row": "R-11"},
    )
    text = render(rows_for(Period.M9, H1_FILED, "100", moved), moved)
    for marker in ("F-OFFICE", "F-PAYER", "F-STAFF", "R-06", "R-08", "R-11", "R-12", "R-13",
                   "R-141", "R-14 ", "R-23", "R-24", "R-25", "R-21"):  # fmt: skip
        assert marker in text, marker
    for stale in ("   - 08 (", "   - 12 (", "   - 23 (", "рядок 06"):
        assert stale not in text


amounts = st.decimals(min_value=D(0), max_value=D("500000"), places=2)


@given(amounts, amounts)
def test_text_carries_exactly_the_state_values(
    previous_income: Decimal, new_income: Decimal
) -> None:
    q1 = rows_for(Period.Q1, None, str(previous_income))
    rows = rows_for(Period.H1, prev_of(q1), str(new_income))
    text = render(rows)
    for amount in (
        rows.income,
        rows.tax_at_rate,
        rows.row_12,
        rows.row_13,
        rows.row_23,
        rows.row_24,
    ):
        assert format_money(amount) in text
    assert ("   - 25 (" in text) == (rows.row_25 > 0)
    assert ("   - 14.1 (" in text) == (rows.row_14 > 0)
    assert PERIOD_LABELS[Period.H1] in text


def test_footer_points_to_the_law_and_official_sites_and_names_no_third_party() -> None:
    text = render(rows_for(Period.Q1, None, "100"))
    assert RULES.links.legislation in text
    assert RULES.links.tax_service in text
    assert "бухгалтером" in text
    assert "Особисто від себе рекомендую" not in text


def test_a_personal_recommendation_appears_when_the_rules_list_one() -> None:
    """A source listed in the rules file is mentioned as a personal recommendation."""
    restored = make_rules(
        recommended_sources=(RecommendedSource(name="Name", url="https://example.test/ch"),),
    )
    text = render(rows_for(Period.Q1, None, "100", restored), restored)
    assert "Особисто від себе рекомендую: Name (https://example.test/ch)." in text
    assert restored.links.legislation in text  # the official sources never go away


def test_estimate_text_also_lists_the_official_sources() -> None:
    rules = make_rules()
    est = estimate(D("1000"), 1, rules)
    text = format_estimate(est, rules)
    assert rules.links.legislation in text
    assert "Особисто від себе рекомендую" not in text
