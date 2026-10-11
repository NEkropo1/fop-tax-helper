"""Monobank personal API: accounts and incoming payments for one account over one time range."""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from mono_it_tax.clients.http import HttpGateway
from mono_it_tax.config.constants.api import (
    MONOBANK_CLIENT_INFO_PATH,
    MONOBANK_MAX_SPAN_S,
    MONOBANK_PAGE_LIMIT,
    MONOBANK_STATEMENT_PATH,
)
from mono_it_tax.config.enums import Currency, Service
from mono_it_tax.domain.account import ClientInfo
from mono_it_tax.domain.payment import Payment
from mono_it_tax.errors import ApiChangedError

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class StatementResult:
    items_received: int  # every item the bank returned (both directions)
    incoming: tuple[Payment, ...]  # amount > 0 only, deduplicated by id, oldest first


class MonobankClient:
    def __init__(self, gateway: HttpGateway) -> None:
        self._gateway = gateway

    def client_info(self) -> ClientInfo:
        raw = self._gateway.get_json(MONOBANK_CLIENT_INFO_PATH, MONOBANK_CLIENT_INFO_PATH)
        try:
            return ClientInfo.model_validate(raw)
        except ValidationError as exc:
            raise self._changed(MONOBANK_CLIENT_INFO_PATH) from exc

    def statement(
        self, account_id: str, account_currency: Currency, start: datetime, end: datetime
    ) -> StatementResult:
        """Incoming payments in [start, end]. One call spans at most 31 days + 1 hour (the caller
        requests month-sized ranges); pages of 500 items are followed backwards in time."""
        start_ts, end_ts = int(start.timestamp()), int(end.timestamp())
        if end_ts - start_ts > MONOBANK_MAX_SPAN_S:
            raise ValueError("statement range exceeds the API maximum span")
        received = 0
        incoming: dict[str, Payment] = {}
        upper = end_ts
        while True:
            page = self._page(account_id, start_ts, upper)
            received += len(page)
            for item in page:
                if self._amount(item) > 0:
                    payment = self._payment(item, account_id, account_currency)
                    incoming[payment.id] = payment
            if len(page) < MONOBANK_PAGE_LIMIT:
                break
            oldest = min(int(item["time"]) for item in page)
            if oldest >= upper:  # a full page inside one second: cannot page further
                raise self._changed(MONOBANK_STATEMENT_PATH)
            upper = oldest
        ordered = sorted(incoming.values(), key=lambda p: (p.time, p.id))
        return StatementResult(items_received=received, incoming=tuple(ordered))

    def _page(self, account_id: str, start_ts: int, end_ts: int) -> list[dict[str, Any]]:
        path = MONOBANK_STATEMENT_PATH.format(account=account_id, start=start_ts, end=end_ts)
        raw = self._gateway.get_json(path, MONOBANK_STATEMENT_PATH)
        if not isinstance(raw, list) or not all(isinstance(i, dict) for i in raw):
            raise self._changed(MONOBANK_STATEMENT_PATH)
        return raw

    def _amount(self, item: dict[str, Any]) -> int:
        try:
            return int(item["amount"])
        except (KeyError, TypeError, ValueError) as exc:
            raise self._changed(MONOBANK_STATEMENT_PATH) from exc

    def _payment(
        self, item: dict[str, Any], account_id: str, account_currency: Currency
    ) -> Payment:
        try:
            return Payment.from_item(item, account_id, account_currency)
        except (ValidationError, KeyError, TypeError, ValueError) as exc:
            raise self._changed(MONOBANK_STATEMENT_PATH) from exc

    @staticmethod
    def _changed(endpoint: str) -> ApiChangedError:
        return ApiChangedError(service=Service.MONOBANK.value, endpoint=endpoint)
