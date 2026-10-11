"""A bank payment: every field the bank returned, typed, plus the verbatim raw item."""

from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from mono_it_tax.config.enums import Currency
from mono_it_tax.config.rules import InternalTransferRule
from mono_it_tax.domain.currency import currency_from_numeric
from mono_it_tax.domain.months import kyiv_date
from mono_it_tax.errors import UnsupportedCurrencyError

# Raw bank keys that Payment decodes into typed fields; anything else is shown as-is, never dropped.
DECODED_RAW_KEYS = frozenset(
    {
        "id", "time", "description", "comment", "mcc", "originalMcc", "amount", "operationAmount",
        "currencyCode", "commissionRate", "cashbackAmount", "balance", "hold", "receiptId",
        "invoiceId", "counterName", "counterEdrpou", "counterIban",
    }
)  # fmt: skip


class Payment(BaseModel):
    """`amount` is in minor units (kopiykas/cents) of the ACCOUNT currency, which `currency` names.
    `operation_amount` / `operation_currency` describe the original operation (e.g. a USD payment
    credited to a UAH card as UAH); the bank's own `currencyCode` is the operation currency."""

    model_config = ConfigDict(frozen=True, populate_by_name=True)

    id: str
    account_id: str
    time: datetime
    amount: int
    currency: Currency
    operation_currency: Currency | None = None  # None: not supported here (still in `raw`)
    description: str | None = None
    comment: str | None = None
    mcc: int | None = None
    original_mcc: int | None = Field(default=None, alias="originalMcc")
    operation_amount: int | None = Field(default=None, alias="operationAmount")
    commission_rate: int | None = Field(default=None, alias="commissionRate")
    cashback_amount: int | None = Field(default=None, alias="cashbackAmount")
    balance: int | None = None
    hold: bool | None = None
    receipt_id: str | None = Field(default=None, alias="receiptId")
    invoice_id: str | None = Field(default=None, alias="invoiceId")
    counter_name: str | None = Field(default=None, alias="counterName")
    counter_edrpou: str | None = Field(default=None, alias="counterEdrpou")
    counter_iban: str | None = Field(default=None, alias="counterIban")
    raw: dict[str, Any]

    @field_validator("time", mode="before")
    @classmethod
    def _unix_to_utc(cls, v: object) -> object:
        return datetime.fromtimestamp(v, UTC) if isinstance(v, int) else v

    @classmethod
    def from_item(
        cls, item: Mapping[str, Any], account_id: str, account_currency: Currency
    ) -> "Payment":
        """Parse one raw statement item of an account kept in `account_currency`. Raises
        pydantic.ValidationError if the shape drifted."""
        return cls.model_validate(
            {
                **item,
                "account_id": account_id,
                "currency": account_currency,
                "operation_currency": _operation_currency(item.get("currencyCode")),
                "raw": dict(item),
            }
        )

    @property
    def tax_date(self) -> date:
        return kyiv_date(self.time)

    @property
    def extra_raw(self) -> dict[str, Any]:
        """Non-empty bank fields this app does not decode (fields the API may add later)."""
        return {
            k: v for k, v in self.raw.items() if k not in DECODED_RAW_KEYS and v not in (None, "")
        }

    @property
    def is_incoming(self) -> bool:
        return self.amount > 0


def _operation_currency(code: object) -> Currency | None:
    if not isinstance(code, int):
        return None
    try:
        return currency_from_numeric(code)
    except UnsupportedCurrencyError:
        return None


def is_possible_internal_transfer(payment: Payment, rule: InternalTransferRule) -> bool:
    """Hint only (the human decides): looks like a move between the user's own cards."""
    return payment.mcc == rule.mcc and (payment.description or "").startswith(
        rule.description_prefixes
    )
