from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from mono_it_tax.config.constants.money import MONEY_QUANTUM
from mono_it_tax.config.enums import Currency, Period, Tax
from mono_it_tax.domain.declaration import build_declaration
from mono_it_tax.domain.estimate import estimate
from mono_it_tax.domain.income import Mark, counted_amount, income_uah, to_uah
from mono_it_tax.domain.money import minor_to_decimal, round_money
from mono_it_tax.domain.months import Month
from mono_it_tax.domain.payment import Payment
from mono_it_tax.domain.payment_plan import build_plan, next_working_day
from mono_it_tax.errors import RateMissingError
from mono_it_tax.services.reports import income_in
from mono_it_tax.store.document import YearDocument
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
    assert by_tax[Tax.ESV].due == date(2026, 10, 20)
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
    assert esv.due == date(2027, 1, 20)


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


# --- Each receipt is rounded to kopiykas BEFORE summing -------------------------------------------

ACC = "acc-1"
USD_DAY = date(2026, 3, 10)


def usd_payment(item_id: str, cents: int, *, month: int = 3, day: int = 10) -> Payment:
    start = Month(2026, month).start_utc.timestamp()
    return make_payment(
        item_id, int(start) + (day - 1) * 86_400 + 43_200, cents, currency=Currency.USD
    )


def doc_with(payments: list[Payment], rates: dict[date, Decimal]) -> YearDocument:
    doc = YearDocument(year=2026)
    doc.payments = {p.id: p for p in payments}
    doc.marks = {p.id: Mark(payment_id=p.id) for p in payments}
    doc.rates = {Currency.USD: rates}
    return doc


def test_receipt_is_rounded_half_up_to_kopiykas_before_anything_else() -> None:
    rates = {Currency.USD: {USD_DAY: D("41.12345")}}
    entry = to_uah(D("100.00"), Currency.USD, USD_DAY, rates)
    assert entry == D("4112.35")  # exactly .345 rounds up
    assert entry != D("4112.345")  # the unrounded product is never returned
    assert entry.as_tuple().exponent == MONEY_QUANTUM.as_tuple().exponent


def test_a_receipt_that_rounds_down() -> None:
    rates = {Currency.USD: {USD_DAY: D("41.12344")}}
    assert to_uah(D("100.00"), Currency.USD, USD_DAY, rates) == D("4112.34")


def test_a_uah_amount_with_extra_digits_is_rounded_too() -> None:
    payment = make_payment(amount=100_000)
    corrected = Mark(payment_id="p1", amount_override=D("100.005"))
    assert income_uah(payment, corrected, {}) == D("100.01")
    assert to_uah(D("12.5"), Currency.UAH, USD_DAY, {}) == D("12.50")


def test_three_receipts_sum_the_rounded_entries_not_the_rounded_sum() -> None:
    payments = [usd_payment(f"r{i}", 10_000) for i in range(3)]
    doc = doc_with(payments, {USD_DAY: D("41.12345")})
    income = income_in(doc, [ACC], [Month(2026, 3)])
    assert income == D("12337.05")  # 3 x 4112.35; rounding only the sum gave 12337.04
    assert income == 3 * round_money(D("100.00") * D("41.12345"))

    rows = build_declaration(Period.Q1, 2026, income, None, RULES)
    assert rows.income == D("12337.05")
    assert rows.tax_at_rate == round_money(D("12337.05") * RULES.single_tax.rate) == D("616.85")
    assert rows.row_23 == round_money(D("12337.05") * RULES.military_levy_rate) == D("123.37")


def test_mixed_receipts_on_different_dates_and_rates() -> None:
    receipts = [
        (usd_payment("a", 1_234, day=5), D("40.15")),
        (usd_payment("b", 99_999, day=6), D("41.98765")),
        (usd_payment("c", 1, day=7), D("39.5")),
    ]
    rates = {p.tax_date: rate for p, rate in receipts}
    doc = doc_with([p for p, _ in receipts], rates)
    expected = sum(
        (round_money(minor_to_decimal(p.amount) * rate) for p, rate in receipts), start=D(0)
    )
    assert income_in(doc, [ACC], [Month(2026, 3)]) == expected


cents = st.integers(min_value=1, max_value=10_000_000)
fx = st.decimals(min_value=D("20"), max_value=D("60"), places=5)


@given(
    st.lists(st.tuples(cents, fx), min_size=1, max_size=12), st.integers(min_value=1, max_value=6)
)
def test_income_is_the_sum_of_per_receipt_rounded_entries(
    receipts: list[tuple[int, Decimal]], split: int
) -> None:
    payments, rates = [], {}
    for index, (minor, rate) in enumerate(receipts):
        month, day = 1 + index % 6, 1 + index  # distinct days, so every receipt has its own rate
        payment = usd_payment(f"r{index}", minor, month=month, day=day)
        payments.append(payment)
        rates[payment.tax_date] = rate
    doc = doc_with(payments, rates)
    everything = [Month(2026, m) for m in range(1, 7)]

    expected = sum(
        (round_money(minor_to_decimal(p.amount) * rates[p.tax_date]) for p in payments), start=D(0)
    )
    total = income_in(doc, [ACC], everything)
    assert total == expected
    assert total == round_money(total)  # no sub-kopiyka digits survive the sum

    first, second = everything[:split], everything[split:]  # Q1 + Q2 == H1, no kopiyka drift
    assert income_in(doc, [ACC], first) + income_in(doc, [ACC], second) == total
