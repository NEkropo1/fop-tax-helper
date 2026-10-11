"""Explicit store migrations: schema_version N -> N + 1, applied on load, never in place on disk."""

from collections.abc import Callable
from typing import Any

from mono_it_tax.domain.currency import currency_from_numeric
from mono_it_tax.errors import UnsupportedCurrencyError


def v1_to_v2(payload: dict[str, Any]) -> dict[str, Any]:
    """v1 stored the bank's `currencyCode` (the OPERATION currency) as the payment currency, but
    `amount` is in the ACCOUNT currency. Make `currency` the account's and keep the old value as
    `operation_currency`. A payment whose account is not cached keeps its currency unchanged."""
    account_currency: dict[str, str] = {}
    for account in payload.get("accounts", []):
        try:
            account_currency[account["id"]] = currency_from_numeric(account["currency_code"]).value
        except (KeyError, UnsupportedCurrencyError):
            continue
    payments = {}
    for payment_id, payment in payload.get("payments", {}).items():
        operation = payment["currency"]
        payments[payment_id] = {
            **payment,
            "currency": account_currency.get(payment["account_id"], operation),
            "operation_currency": operation,
        }
    return {**payload, "payments": payments, "schema_version": 2}


MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {1: v1_to_v2}
