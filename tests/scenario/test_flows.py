"""End-to-end flows through the composition root with a fake bank, fake clock, tmp_path store."""

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from mono_it_tax.config.enums import Coverage, Currency, MonthState, Period
from mono_it_tax.domain.declaration import PreviousDeclaration
from mono_it_tax.domain.ledger import coverage
from mono_it_tax.domain.months import Month
from mono_it_tax.domain.periods import MonthsSelection, PeriodSelection
from mono_it_tax.errors import (
    ConfigRulesMissingError,
    ConfigTokenMissingError,
    DeclRowMismatchError,
    MonthsNotReviewedError,
    NetworkError,
    RateMissingError,
    TokenRejectedError,
    UnsupportedCurrencyError,
)
from mono_it_tax.pipelines.fetch import months_to_fetch
from mono_it_tax.services.fetch import FetchProgress
from mono_it_tax.services.marking import month_payments, state_of
from mono_it_tax.startup import App
from mono_it_tax.store.year_store import YearStore
from tests.scenario.fake_bank import FakeBank, bank_item, kyiv_ts, make_app
from tests.support import FakeClock, json_response

D = Decimal
UAH_ACC, USD_ACC = "acc-1", "acc-2"
BOTH = [UAH_ACC, USD_ACC]
M9 = PeriodSelection(2026, Period.M9)


def bank_with_q3_income() -> FakeBank:
    bank = FakeBank()
    bank.add(UAH_ACC, bank_item("jul", kyiv_ts(2026, 7, 10), 100_000))  # 1000.00
    bank.add(UAH_ACC, bank_item("aug", kyiv_ts(2026, 8, 5), 250_000))  # 2500.00
    bank.add(UAH_ACC, bank_item("sep-late", kyiv_ts(2026, 9, 30, 23, 30), 50_000))  # 500.00
    bank.add(UAH_ACC, bank_item("oct-first", kyiv_ts(2026, 10, 1, 0, 30), 70_000))  # October!
    bank.add(UAH_ACC, bank_item("spend", kyiv_ts(2026, 8, 6), -99_999))  # outgoing: never kept
    bank.add(USD_ACC, bank_item("usd", kyiv_ts(2026, 8, 15), 10_000, currency_code=840))  # $100
    return bank


def fetch_all(app: App, selection: PeriodSelection | MonthsSelection, accounts: list[str]) -> None:
    plan = app.fetch_pipeline.prepare(selection, accounts)
    outcome = app.fetch_pipeline.execute(selection, plan)
    assert not outcome.cancelled


def mark_everything(app: App, year: int = 2026) -> None:
    app.marking.mark(year, list(app.store.load(year).payments))


def review_all(
    app: App,
    selection: PeriodSelection | MonthsSelection,
    accounts: list[str],
    *,
    with_history: bool = False,
) -> None:
    """The human's 'income marked, done' for every account-month the result depends on."""
    for account in accounts:
        for month in months_to_fetch(selection, with_history=with_history):
            app.marking.review_month(2026, account, month)


H1_TYPED = PreviousDeclaration(
    Period.H1, D("200000.00"), D(0), D("10000.00"), D("2000.00")
)  # as copied from the filed half-year declaration


def test_path_a_nine_months_fetches_only_the_new_quarter(tmp_path: Path) -> None:
    bank = bank_with_q3_income()
    app, clock = make_app(tmp_path, bank)
    app.accounts.accounts(2026)
    plan = app.fetch_pipeline.prepare(M9, BOTH)
    assert len(plan.tasks) == 6  # 3 months x 2 accounts: Apr-Jun is NOT requested
    assert plan.eta_seconds == 360.0
    progress: list[FetchProgress] = []
    outcome = app.fetch_pipeline.execute(M9, plan, on_progress=progress.append)
    assert (outcome.completed, outcome.total, outcome.cancelled) == (6, 6, False)
    assert [p.done for p in progress] == [1, 2, 3, 4, 5, 6]
    assert bank.client_info_calls == 1
    assert sum(clock.slept) == 360.0  # 7 requests, 60 s apart: the bank's limit is respected
    starts = {Month(2026, m).start_utc.timestamp() for m in (7, 8, 9)}
    assert {call[1] for call in bank.statement_calls} == starts

    doc = app.store.load(2026)
    assert set(doc.payments) == {"jul", "aug", "sep-late", "usd"}  # incoming only, no October
    mark_everything(app)
    review_all(app, M9, BOTH)
    help_ = app.report_pipeline.declaration_help(2026, Period.M9, BOTH, app.rules, H1_TYPED)
    rows = help_.rows
    assert rows.income == D("208015.00")  # 200000 + 1000 + 2500 + 500 + $100 x 40.15
    assert (rows.row_12, rows.row_13, rows.row_14) == (D("10400.75"), D("10000.00"), D("400.75"))
    assert (rows.row_23, rows.row_24, rows.row_25) == (D("2080.15"), D("2000.00"), D("80.15"))
    assert not help_.preliminary
    assert "400.75" in help_.text
    assert "5 707.02" in help_.text
    assert len(bank.nbu_calls) == 1  # one NBU request for the one foreign day


def test_quarter_without_new_income_owes_only_esv(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, FakeBank())
    fetch_all(app, M9, [UAH_ACC])
    review_all(app, M9, [UAH_ACC])  # confirmed: no income this quarter
    help_ = app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules, H1_TYPED)
    assert (help_.rows.row_14, help_.rows.row_25) == (D(0), D(0))
    assert help_.rows.income == D("200000.00")
    assert "платити нічого" in help_.text
    assert "19.10.2026" in help_.text
    assert "09.11.2026" in help_.text


def test_already_answered_months_cost_nothing_even_when_empty(tmp_path: Path) -> None:
    bank = FakeBank()
    app, _ = make_app(tmp_path, bank)
    fetch_all(app, M9, [UAH_ACC])
    doc = app.store.load(2026)
    assert all(coverage(doc.ledger, UAH_ACC, m) is Coverage.FULL for m in M9.months)
    assert app.fetch_pipeline.prepare(M9, [UAH_ACC]).tasks == ()
    calls_before = len(bank.statement_calls)
    outcome = app.fetch_pipeline.execute(M9, app.fetch_pipeline.prepare(M9, [UAH_ACC]))
    assert outcome.total == 0
    assert len(bank.statement_calls) == calls_before


def test_failure_in_the_middle_keeps_what_was_answered_and_resumes(tmp_path: Path) -> None:
    bank = bank_with_q3_income()
    app, _ = make_app(tmp_path, bank)
    bank.statement_hook = lambda n: httpx.ConnectTimeout("down") if n in {2, 3, 4} else None
    plan = app.fetch_pipeline.prepare(M9, [UAH_ACC])
    with pytest.raises(NetworkError) as exc:
        app.fetch_pipeline.execute(M9, plan)
    assert exc.value.params["attempts"] == "3"
    assert "acc-1" not in str(exc.value)
    assert len(app.store.load(2026).ledger) == 1  # month 1 was saved
    remaining = app.fetch_pipeline.prepare(M9, [UAH_ACC])
    assert len(remaining.tasks) == 2
    app.fetch_pipeline.execute(M9, remaining)
    assert len(app.store.load(2026).ledger) == 3


def test_cancel_between_requests_loses_nothing(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_q3_income())
    plan = app.fetch_pipeline.prepare(M9, [UAH_ACC])
    done: list[FetchProgress] = []
    outcome = app.fetch_pipeline.execute(
        M9, plan, on_progress=done.append, should_cancel=lambda: len(done) >= 1
    )
    assert (outcome.completed, outcome.cancelled) == (1, True)
    assert len(app.store.load(2026).ledger) == 1


def test_rejected_token_fails_once_and_stores_nothing(tmp_path: Path) -> None:
    bank = bank_with_q3_income()
    bank.statement_hook = lambda _n: json_response({"errorDescription": "bad"}, 403)
    app, _ = make_app(tmp_path, bank)
    with pytest.raises(TokenRejectedError):
        app.fetch_pipeline.execute(M9, app.fetch_pipeline.prepare(M9, [UAH_ACC]))
    assert len(bank.statement_calls) == 1
    assert app.store.load(2026).ledger == []


def test_unsupported_incoming_currency_saves_nothing_for_that_request(tmp_path: Path) -> None:
    bank = FakeBank()
    bank.add(UAH_ACC, bank_item("weird", kyiv_ts(2026, 7, 3), 500, currency_code=999))
    app, _ = make_app(tmp_path, bank)
    with pytest.raises(UnsupportedCurrencyError):
        app.fetch_pipeline.execute(M9, app.fetch_pipeline.prepare(M9, [UAH_ACC]))
    doc = app.store.load(2026)
    assert doc.ledger == []
    assert doc.payments == {}


def test_a_failed_save_never_leaves_coverage_without_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = make_app(tmp_path, bank_with_q3_income())
    plan = app.fetch_pipeline.prepare(M9, [UAH_ACC])
    real_save = YearStore.save

    def broken_save(self: YearStore, doc: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(YearStore, "save", broken_save)
    with pytest.raises(OSError, match="disk full"):
        app.fetch_pipeline.execute(M9, plan)
    monkeypatch.setattr(YearStore, "save", real_save)
    doc = app.store.load(2026)
    assert doc.ledger == [] and doc.payments == {}  # noqa: PT018
    assert len(app.fetch_pipeline.prepare(M9, [UAH_ACC]).tasks) == 3  # all still to fetch


def test_payment_just_after_kyiv_midnight_belongs_to_the_new_month(tmp_path: Path) -> None:
    bank = FakeBank()
    bank.add(UAH_ACC, bank_item("late-mar", kyiv_ts(2026, 3, 31, 23, 59), 100))
    bank.add(UAH_ACC, bank_item("early-apr", kyiv_ts(2026, 4, 1, 0, 30), 200))  # still 31 Mar UTC
    app, _ = make_app(tmp_path, bank)
    selection = MonthsSelection((Month(2026, 3), Month(2026, 4)))
    fetch_all(app, selection, [UAH_ACC])
    doc = app.store.load(2026)
    assert [p.id for p in month_payments(doc, UAH_ACC, Month(2026, 3))] == ["late-mar"]
    assert [p.id for p in month_payments(doc, UAH_ACC, Month(2026, 4))] == ["early-apr"]


def test_month_review_lifecycle(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_q3_income())
    july = Month(2026, 7)
    with pytest.raises(ValueError, match="cannot review"):
        app.marking.review_month(2026, UAH_ACC, july)
    fetch_all(app, M9, [UAH_ACC])
    assert state_of(app.store.load(2026), UAH_ACC, july) is MonthState.FETCHED
    app.marking.review_month(2026, UAH_ACC, july)
    assert state_of(app.store.load(2026), UAH_ACC, july) is MonthState.REVIEWED


def test_months_mode_converts_foreign_income_once_and_caches_rates(tmp_path: Path) -> None:
    bank = bank_with_q3_income()
    app, _ = make_app(tmp_path, bank)
    selection = MonthsSelection((Month(2026, 8),))
    fetch_all(app, selection, BOTH)
    mark_everything(app)
    review_all(app, selection, BOTH)
    text = app.report_pipeline.months_report(selection, BOTH, app.rules)
    assert "6 515.00" in text  # 2500.00 + $100 x 40.15
    assert len(bank.nbu_calls) == 1
    assert bank.nbu_calls[0]["valcode"] == "usd"
    app.report_pipeline.months_report(selection, BOTH, app.rules)
    assert len(bank.nbu_calls) == 1  # past rates never change: cached
    assert app.store.load(2026).rates[Currency.USD][date(2026, 8, 15)] == D("40.15")


def test_missing_nbu_rate_is_an_error_not_a_guess(tmp_path: Path) -> None:
    bank = bank_with_q3_income()
    bank.nbu_missing_days = {date(2026, 8, 15)}
    app, _ = make_app(tmp_path, bank)
    selection = MonthsSelection((Month(2026, 8),))
    fetch_all(app, selection, [USD_ACC])
    mark_everything(app)
    review_all(app, selection, [USD_ACC])
    with pytest.raises(RateMissingError):
        app.report_pipeline.months_report(selection, [USD_ACC], app.rules)


def bank_with_history() -> FakeBank:
    bank = FakeBank()
    for number, (month, amount) in enumerate([(2, 10_000_000), (5, 5_000_000), (8, 2_500_000)]):
        bank.add(UAH_ACC, bank_item(f"h{number}", kyiv_ts(2026, month, 10), amount))
    return bank


def test_path_b_computes_previous_from_bank_data_and_equals_path_a(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_history())
    plan = app.fetch_pipeline.prepare(M9, [UAH_ACC], with_history=True)
    assert len(plan.tasks) == 9  # Jan..Sep
    app.fetch_pipeline.execute(M9, plan)
    mark_everything(app)
    review_all(app, M9, [UAH_ACC], with_history=True)
    computed = app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules)
    typed = PreviousDeclaration(Period.H1, D("150000.00"), D(0), D("7500.00"), D("1500.00"))
    app2, _ = make_app(tmp_path / "second", bank_with_history())
    fetch_all(app2, M9, [UAH_ACC])
    mark_everything(app2)
    review_all(app2, M9, [UAH_ACC])
    via_typed = app2.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app2.rules, typed)
    assert computed.rows == via_typed.rows
    assert computed.rows.income == D("175000.00")


def test_typed_value_filed_with_the_tax_office_wins_over_computed(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_history())
    plan = app.fetch_pipeline.prepare(M9, [UAH_ACC], with_history=True)
    app.fetch_pipeline.execute(M9, plan)
    mark_everything(app)
    review_all(app, M9, [UAH_ACC], with_history=True)
    filed = PreviousDeclaration(Period.H1, D("160000.00"), D(0), D("8000.00"), D("1600.00"))
    app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules, filed)
    later = app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules)
    assert later.rows.income == D(
        "185000.00"
    )  # 160000 (filed) + 25000 (new), not the computed 175000


def test_bad_typed_rows_are_rejected_before_anything_is_stored(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, FakeBank())
    wrong = PreviousDeclaration(Period.H1, D("200000.00"), D(0), D("9999.99"), D("2000.00"))
    with pytest.raises(DeclRowMismatchError):
        app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules, wrong)
    assert app.store.load(2026).declarations == []


def test_an_unfinished_period_is_marked_preliminary(tmp_path: Path) -> None:
    clock = FakeClock(datetime(2026, 2, 1, tzinfo=UTC))
    app, _ = make_app(tmp_path, FakeBank(), clock=clock)
    selection = PeriodSelection(2026, Period.Q1)
    fetch_all(app, selection, [UAH_ACC])
    review_all(app, selection, [UAH_ACC])
    help_ = app.report_pipeline.declaration_help(2026, Period.Q1, [UAH_ACC], app.rules)
    assert help_.preliminary


def test_first_period_of_the_year_needs_no_previous(tmp_path: Path) -> None:
    bank = FakeBank()
    bank.add(UAH_ACC, bank_item("q1", kyiv_ts(2026, 2, 3), 1_000_000))
    app, _ = make_app(tmp_path, bank)
    selection = PeriodSelection(2026, Period.Q1)
    fetch_all(app, selection, [UAH_ACC])
    mark_everything(app)
    review_all(app, selection, [UAH_ACC])
    rows = app.report_pipeline.declaration_help(2026, Period.Q1, [UAH_ACC], app.rules).rows
    assert (rows.row_14, rows.row_25) == (D("500.00"), D("100.00"))


def test_startup_fails_fast_with_actionable_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigTokenMissingError):
        make_app(tmp_path, FakeBank(), credential="   ")
    with pytest.raises(ConfigRulesMissingError):
        make_app(tmp_path, FakeBank(), year=2031)


def test_the_store_key_is_created_at_startup_and_data_is_encrypted(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_q3_income())
    fetch_all(app, M9, [UAH_ACC])
    assert app.key_provider.name == "keyring"
    blob = app.store.path(2026).read_bytes()
    assert b"sep-late" not in blob


def test_unconfirmed_months_are_an_error_not_silent_zero_income(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_q3_income())
    fetch_all(app, M9, [UAH_ACC])
    mark_everything(app)  # marked, but the human has not pressed "done"
    with pytest.raises(MonthsNotReviewedError) as exc:
        app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules, H1_TYPED)
    assert exc.value.params["months"] == "2026-07, 2026-08, 2026-09"
    app.marking.review_month(2026, UAH_ACC, Month(2026, 7))
    with pytest.raises(MonthsNotReviewedError) as partial:
        app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules, H1_TYPED)
    assert partial.value.params["months"] == "2026-08, 2026-09"


def test_months_estimate_also_requires_confirmed_months(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_q3_income())
    selection = MonthsSelection((Month(2026, 8),))
    fetch_all(app, selection, [UAH_ACC])
    with pytest.raises(MonthsNotReviewedError):
        app.report_pipeline.months_report(selection, [UAH_ACC], app.rules)


def test_path_b_refuses_to_compute_from_history_that_was_never_confirmed(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, bank_with_history())
    fetch_all(app, M9, [UAH_ACC])  # only Jul-Sep fetched: Jan-Jun are unknown, not zero
    mark_everything(app)
    review_all(app, M9, [UAH_ACC])
    with pytest.raises(MonthsNotReviewedError) as exc:
        app.report_pipeline.declaration_help(2026, Period.M9, [UAH_ACC], app.rules)
    assert exc.value.params["months"] == "2026-01, 2026-02, 2026-03, 2026-04, 2026-05, 2026-06"
