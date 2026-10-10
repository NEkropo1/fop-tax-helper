from decimal import Decimal
from pathlib import Path

import pytest

from mono_it_tax.clock import SystemClock
from mono_it_tax.config.enums import Period
from mono_it_tax.copy.declaration_uk import FIRST_PERIOD_NOTE, previous_report_request
from mono_it_tax.domain.periods import PeriodSelection
from tests.scenario.fake_bank import FakeBank, bank_item, kyiv_ts, make_app

D = Decimal


def test_accounts_are_fetched_once_cached_and_chosen_per_year(tmp_path: Path) -> None:
    bank = FakeBank()
    app, _ = make_app(tmp_path, bank)
    first = app.accounts.accounts(2026)
    assert [a.id for a in first] == ["acc-1", "acc-2"]
    assert app.accounts.accounts(2026) == first
    assert bank.client_info_calls == 1  # cached: the 60 s limit is not spent twice
    app.accounts.accounts(2026, refresh=True)
    assert bank.client_info_calls == 2
    app.accounts.choose(2026, ["acc-2", "acc-1", "acc-2"])
    assert app.store.load(2026).tax_accounts == ("acc-2", "acc-1")


def test_marking_unmarking_and_amount_corrections(tmp_path: Path) -> None:
    bank = FakeBank()
    bank.add("acc-1", bank_item("p1", kyiv_ts(2026, 7, 10), 100_000))
    bank.add("acc-1", bank_item("p2", kyiv_ts(2026, 7, 11), 200_000))
    app, _ = make_app(tmp_path, bank)
    selection = PeriodSelection(2026, Period.M9)
    app.fetch_pipeline.execute(selection, app.fetch_pipeline.prepare(selection, ["acc-1"]))

    app.marking.mark(2026, ["p1", "p2"])
    app.marking.mark(2026, ["p1"])  # marking twice changes nothing
    assert set(app.store.load(2026).marks) == {"p1", "p2"}

    app.marking.set_amount(2026, "p2", D("150.50"))
    assert app.store.load(2026).marks["p2"].amount_override == D("150.50")
    app.marking.set_amount(2026, "p2", None)
    assert app.store.load(2026).marks["p2"].amount_override is None

    app.marking.unmark(2026, ["p1", "never-marked"])
    assert set(app.store.load(2026).marks) == {"p2"}


def test_unknown_payment_cannot_be_marked_or_corrected(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, FakeBank())
    with pytest.raises(KeyError):
        app.marking.mark(2026, ["ghost"])
    with pytest.raises(KeyError):
        app.marking.set_amount(2026, "ghost", D("1"))


def test_previous_report_request_names_the_rows_to_copy(tmp_path: Path) -> None:
    app, _ = make_app(tmp_path, FakeBank())
    text = previous_report_request(Period.H1, 2026, app.rules)
    assert app.rules.links.cabinet in text
    for row in ("06", "07", "12", "23"):
        assert f"рядок {row}" in text
    assert previous_report_request(None, 2026, app.rules) == FIRST_PERIOD_NOTE


def test_system_clock_is_aware_and_monotonic() -> None:
    clock = SystemClock()
    assert clock.now().tzinfo is not None
    first = clock.monotonic()
    clock.sleep(0)
    assert clock.monotonic() >= first
