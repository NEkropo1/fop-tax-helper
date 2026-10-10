"""NBU official rates: one request per currency for a date range (every calendar day)."""

from datetime import UTC, date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, ValidationError

from mono_it_tax.clients.http import HttpGateway
from mono_it_tax.config.constants.api import (
    NBU_DATE_PARAM_FORMAT,
    NBU_DATE_RESPONSE_FORMAT,
    NBU_RANGE_PARAMS,
    NBU_RANGE_PATH,
)
from mono_it_tax.config.enums import Currency, Service
from mono_it_tax.errors import ApiChangedError


class _RateRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    exchangedate: str
    rate_per_unit: Decimal


def _parse_rows(raw: object) -> dict[date, Decimal]:
    if not isinstance(raw, list):
        raise TypeError("NBU response is not a list")
    rows = (_RateRow.model_validate(item) for item in raw)
    return {
        datetime.strptime(r.exchangedate, NBU_DATE_RESPONSE_FORMAT)
        .replace(tzinfo=UTC)
        .date(): r.rate_per_unit
        for r in rows
    }


class NbuClient:
    def __init__(self, gateway: HttpGateway) -> None:
        self._gateway = gateway

    def rates(self, currency: Currency, start: date, end: date) -> dict[date, Decimal]:
        params = {
            **NBU_RANGE_PARAMS,
            "start": start.strftime(NBU_DATE_PARAM_FORMAT),
            "end": end.strftime(NBU_DATE_PARAM_FORMAT),
            "valcode": currency.value.lower(),
        }
        raw = self._gateway.get_json(NBU_RANGE_PATH, NBU_RANGE_PATH, params)
        try:
            return _parse_rows(raw)
        except (ValidationError, TypeError, ValueError) as exc:
            raise ApiChangedError(service=Service.NBU.value, endpoint=NBU_RANGE_PATH) from exc
