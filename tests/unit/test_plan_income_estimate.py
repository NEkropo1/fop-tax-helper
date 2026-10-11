from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from mono_it_tax.config.enums import Currency, Period, Tax
from mono_it_tax.domain.declaration import build_declaration
from mono_it_tax.domain.estimate import estimate
from mono_it_tax.domain.income import Mark, counted_amount, income_uah, to_uah
from mono_it_tax.domain.payment_plan import build_plan, next_working_day
from mono_it_tax.errors import RateMissingError
from tests.support import make_payment, make_rules

D = Decimal
RULES = make_rules()


def test_weekend_deadline_moves_to_monday() -> None:
    assert next_working_day(date(2026, 8, 9)) == date(2026, 8, 10)  # Sunday
    assert next_working_day(date(2026, 8, 8)) == date(2026, 8, 10)  # Saturday
    assert next_working_day(date(2026, 8, 10)) == date(2026, 8, 10)  # Monday stays


def test_third_quarter_2026_matches_the_accountants_note() -> None:
    rows = build_declaration(Period.Q1, 2026, D(0), None, RULES)
    rows = type(rows)(**{**rows.__dict__, "period": Period.M9})
    plan = build_plan(rows, RULES)
    by_tax = {p.tax: p for p in plan.payments}
    assert by_tax[Tax.ESV].amount == D("5707.02")
    assert by_tax[Tax.ESV].due == date(2026, 10, 19)
    assert plan.declaration_due == date(2026, 11, 9)
    assert by_tax[Tax.SINGLE_TAX].due == by_tax[Tax.MILITARY_LEVY].due == date(2026, 11, 19)
    assert by_tax[Tax.SINGLE_TAX].budget_code == RULES.budget_codes[Tax.SINGLE_TAX]


def test_half_year_declaration_deadline_shifts_off_sunday() -> None:
    rows = build_declaration(Period.Q1, 2026, D(0), None, RULES)
    h1 = type(rows)(**{**rows.__dict__, "period": Period.H1})
    assert build_plan(h1, RULES).declaration_due == date(2026, 8, 10)


def test_annual_esv_falls_in_january_of_next_year() -> None:
    rows = build_declaration(Period.Q1, 2026, D(0), None, RULES)
    year_rows = type(rows)(**{**rows.__dict__, "period": Period.Y})
    esv = next(p for p in build_plan(year_rows, RULES).payments if p.tax is Tax.ESV)
    assert esv.due == date(2027, 1, 19)


def test_counted_amount_uses_override_else_bank_amount() -> None:
    payment = make_payment(amount=123_456)
    assert counted_amount(payment, Mark(payment_id="p1")) == D("1234.56")
    assert counted_amount(payment, Mark(payment_id="p1", amount_override=D("1000"))) == D("1000")


def test_override_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        Mark(payment_id="p1", amount_override=D("0"))


def test_foreign_income_uses_the_rate_of_the_receipt_day() -> None:
    # 2026-09-30 21:30 UTC is 00:30 on 1 October in Kyiv: the Oct 1 rate applies
    payment = make_payment(amount=10_000, currency=Currency.USD, unix_time=1_790_803_800)
    assert payment.tax_date == date(2026, 10, 1)
    rates = {Currency.USD: {date(2026, 9, 30): D("1"), date(2026, 10, 1): D("41.5")}}
    assert income_uah(payment, Mark(payment_id="p1"), rates) == D("4150.0")


def test_missing_rate_fails_loudly() -> None:
    with pytest.raises(RateMissingError) as exc:
        to_uah(D("1"), Currency.EUR, date(2026, 1, 1), {})
    assert exc.value.params == {"currency": "EUR", "date": "2026-01-01"}


def test_uah_needs_no_rate() -> None:
    assert to_uah(D("12.5"), Currency.UAH, date(2026, 1, 1), {}) == D("12.5")


def test_months_estimate_lists_every_configured_rate() -> None:
    est = estimate(D("100000"), 3, RULES)
    assert (est.military_levy, est.esv) == (D("1000.00"), D("5707.02"))
    assert [(r.rate, r.single_tax, r.total) for r in est.by_rate] == [
        (D("0.03"), D("3000.00"), D("9707.02")),
        (D("0.05"), D("5000.00"), D("11707.02")),
        (D("0.15"), D("15000.00"), D("21707.02")),
    ]
    assert [r.rate for r in est.by_rate] == list(RULES.estimate_rates)  # config order, not sorted


def test_estimate_rates_follow_the_rules_file() -> None:
    est = estimate(D("1000"), 1, make_rules(estimate_rates=(D("0.2"),)))
    assert [r.single_tax for r in est.by_rate] == [D("200.00")]


@pytest.mark.parametrize("bad", [(), (D("0"),), (D("1.5"),), (D("0.05"), D("-0.1"))])
def test_estimate_rates_must_be_a_list_of_fractions(bad: tuple[Decimal, ...]) -> None:
    with pytest.raises(ValidationError):
        make_rules(estimate_rates=bad)


def test_zero_income_estimate_is_only_esv() -> None:
    est = estimate(D(0), 1, RULES)
    assert [r.total for r in est.by_rate] == [est.esv] * len(RULES.estimate_rates)
    assert est.esv == D("1902.34")
