import re
from decimal import Decimal
from pathlib import Path
from string import Formatter

import pydantic
import pytest

from mono_it_tax.config.enums import Currency, ErrorCode
from mono_it_tax.config.rules import load_rules
from mono_it_tax.copy.errors_uk import ERROR_TEXTS, LI_LINK_PLACEHOLDER, render_error
from mono_it_tax.domain.money import mask_pan, minor_to_decimal, round_money
from mono_it_tax.domain.payment import Payment, is_possible_internal_transfer
from mono_it_tax.errors import (
    AppError,
    ConfigRulesInvalidError,
    ConfigRulesMissingError,
    UnsupportedCurrencyError,
)
from tests.support import bank_item, make_payment, make_rules

D = Decimal
REAL_RULES_DIR = Path(__file__).resolve().parents[2] / "data" / "rules"


def all_error_classes() -> list[type[AppError]]:
    found: list[type[AppError]] = []
    stack = list(AppError.__subclasses__())
    while stack:
        cls = stack.pop()
        found.append(cls)
        stack.extend(cls.__subclasses__())
    return found


def test_every_error_code_has_a_class_and_a_text() -> None:
    classes = {cls.code for cls in all_error_classes()}
    assert classes == set(ErrorCode)
    assert set(ERROR_TEXTS) == set(ErrorCode)


@pytest.mark.parametrize("cls", all_error_classes(), ids=lambda c: c.__name__)
def test_error_texts_use_only_supplied_placeholders(cls: type[AppError]) -> None:
    template = ERROR_TEXTS[cls.code]
    used = {name for _, name, _, _ in Formatter().parse(template) if name}
    assert used <= set(cls.PARAMS) | {LI_LINK_PLACEHOLDER}
    error = cls(**{param: f"<{param}>" for param in cls.PARAMS})
    text = render_error(error, "https://linkedin.test/me")
    assert "{" not in text
    assert text.strip()


def test_error_requires_exact_params() -> None:
    with pytest.raises(TypeError):
        UnsupportedCurrencyError()
    with pytest.raises(TypeError):
        UnsupportedCurrencyError(code=1, extra=2)


def test_money_helpers() -> None:
    assert minor_to_decimal(123_456) == D("1234.56")
    assert minor_to_decimal(-5) == D("-0.05")
    assert round_money(D("0.005")) == D("0.01")
    assert round_money(D("2.675")) == D("2.68")  # half-up, not banker's
    assert mask_pan("537541******1234") == "5375********1234"
    assert mask_pan("1234") == "****"


def test_payment_keeps_every_field_and_the_raw_item() -> None:
    item = bank_item(
        "x1", counterName="ТОВ Ромашка", counterEdrpou="123", invoiceId="inv", future_field="kept"
    )
    payment = Payment.from_item(item, "acc-9")
    assert payment.counter_name == "ТОВ Ромашка"
    assert payment.invoice_id == "inv"
    assert payment.original_mcc == 4829
    assert payment.account_id == "acc-9"
    assert payment.raw["future_field"] == "kept"  # fields the API adds later are never lost
    assert payment.currency is Currency.UAH


def test_unknown_currency_fails_loudly() -> None:
    with pytest.raises(UnsupportedCurrencyError):
        Payment.from_item(bank_item(currency_code=1), "a")


def test_shape_drift_is_a_validation_error() -> None:
    item = bank_item()
    del item["id"]
    with pytest.raises(pydantic.ValidationError):
        Payment.from_item(item, "a")


def test_internal_transfer_tag_is_only_a_hint_by_mcc_and_wording() -> None:
    rule = make_rules().internal_transfer
    assert is_possible_internal_transfer(make_payment(description="З Білої картки"), rule)
    assert not is_possible_internal_transfer(make_payment(description="Bank of Cats LLC"), rule)
    assert not is_possible_internal_transfer(
        make_payment(description="З Білої картки", mcc=5411), rule
    )


def test_real_2026_rules_file_loads_and_is_versioned() -> None:
    """The only test that reads the repo's data file: a rules edit must keep it loadable."""
    rules = load_rules(REAL_RULES_DIR, 2026)
    assert rules.year == 2026
    assert re.fullmatch(r"\d{4}\.\d+", rules.version)
    assert rules.esv_quarterly == D("5707.02")


def test_missing_and_broken_rules_are_config_errors(tmp_path: Path) -> None:
    with pytest.raises(ConfigRulesMissingError):
        load_rules(tmp_path, 2031)
    (tmp_path / "2032.yaml").write_text("year: [unclosed", encoding="utf-8")
    with pytest.raises(ConfigRulesInvalidError):
        load_rules(tmp_path, 2032)
    (tmp_path / "2033.yaml").write_text("year: 2033\n", encoding="utf-8")
    with pytest.raises(ConfigRulesInvalidError):
        load_rules(tmp_path, 2033)
