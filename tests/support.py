"""Test helpers: fake clock, builders for rules / payments / bank items, mock bank transport."""

import json
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx

from mono_it_tax.config.enums import Currency, Tax
from mono_it_tax.config.rules import (
    Channel,
    Contact,
    Deadlines,
    Declaration,
    DeclarationFields,
    DeclarationRows,
    InternalTransferRule,
    Links,
    Regime,
    Rules,
)
from mono_it_tax.domain.payment import Payment

ACCOUNT = "acc-1"
UAH_CODE = 980
USD_CODE = 840


class FakeClock:
    """Time only moves when someone sleeps: the 60 s throttle is testable in milliseconds."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
        self._mono = 1000.0
        self.slept: list[float] = []

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._mono

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self._mono += seconds
        self._now = datetime.fromtimestamp(self._now.timestamp() + seconds, UTC)

    def advance(self, seconds: float) -> None:
        self._mono += seconds


def make_rules(**overrides: Any) -> Rules:
    base: dict[str, Any] = {
        "version": "test.1",
        "updated_on": "2026-10-10",
        "year": 2026,
        "group": 3,
        "minimum_wage_uah": Decimal("8647"),
        "esv_rate": Decimal("0.22"),
        "single_tax": Regime(
            rate=Decimal("0.05"), income_row="06", tax_row="11", note="no-VAT case"
        ),
        "estimate_rates": (Decimal("0.03"), Decimal("0.05"), Decimal("0.15")),
        "military_levy_rate": Decimal("0.01"),
        "income_limit_uah": Decimal("10091049"),
        "sources": ("https://example.test/source",),
        "deadlines": Deadlines(
            declaration_days_after_quarter_end=40,
            single_tax_days_after_quarter_end=50,
            esv_day_of_next_month=19,
        ),
        "declaration": Declaration(
            form="F0103309",
            order="test order",
            fields=DeclarationFields(office="4", taxpayer="5", employees="9"),
            empty_rows=("01", "07", "09", "14.2", "22"),
            rows=DeclarationRows(
                income_15="07",
                total_income="08",
                tax_total="12",
                tax_previous="13",
                tax_due_base="14.1",
                tax_due_extra="14.2",
                tax_due="14",
                esv_due="21",
                levy_total="23",
                levy_previous="24",
                levy_due="25",
            ),
        ),
        "budget_codes": {
            Tax.ESV: "71040000",
            Tax.SINGLE_TAX: "18050400",
            Tax.MILITARY_LEVY: "11011700",
        },
        "links": Links(
            cabinet="https://cabinet.test/",
            tax_account="https://cabinet.test/tax-account",
            new_declaration="https://cabinet.test/reporting/doc",
            requisites_xlsx="https://tax.test/xlsx",
            declaration_video="https://video.test/watch",
        ),
        "channels": (Channel(name="Chan", url="https://youtube.test/chan"),),
        "contact": Contact(linkedin="https://linkedin.test/author"),
        "internal_transfer": InternalTransferRule(
            mcc=4829, description_prefixes=("З Білої картки",)
        ),
        "disclaimer": "Not tax advice.",
    }
    return Rules.model_validate({**base, **overrides})


def bank_item(
    item_id: str = "p1",
    unix_time: int = 1_790_000_000,
    amount: int = 100_000,
    currency_code: int = UAH_CODE,
    **extra: Any,
) -> dict[str, Any]:
    """A raw statement item as the bank sends it (minor units; page order is the caller's)."""
    return {
        "id": item_id,
        "time": unix_time,
        "description": "Test payment",
        "mcc": 4829,
        "originalMcc": 4829,
        "amount": amount,
        "operationAmount": amount,
        "currencyCode": currency_code,
        "commissionRate": 0,
        "cashbackAmount": 0,
        "balance": 500_000,
        "hold": False,
        **extra,
    }


def make_payment(
    item_id: str = "p1",
    unix_time: int = 1_790_000_000,
    amount: int = 100_000,
    currency: Currency = Currency.UAH,
    account_id: str = ACCOUNT,
    **extra: Any,
) -> Payment:
    code = {Currency.UAH: UAH_CODE, Currency.USD: USD_CODE}[currency]
    item = bank_item(item_id, unix_time, amount, code, **extra)
    return Payment.from_item(item, account_id, currency)


Handler = Callable[[httpx.Request], httpx.Response]


def json_response(
    body: object, status: int = 200, headers: dict[str, str] | None = None
) -> httpx.Response:
    return httpx.Response(status, content=json.dumps(body), headers=headers)
