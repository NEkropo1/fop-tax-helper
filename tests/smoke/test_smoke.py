"""Hits real services. Run by a human only: `uv run pytest -m smoke -o addopts=""`."""

from datetime import date
from decimal import Decimal

import httpx
import pytest

from mono_it_tax.clients.http import HttpGateway, RetryPolicy
from mono_it_tax.clients.monobank import MonobankClient
from mono_it_tax.clients.nbu import NbuClient
from mono_it_tax.clock import SystemClock
from mono_it_tax.config.constants.api import (
    MONOBANK_BASE_URL,
    MONOBANK_MIN_INTERVAL_S,
    MONOBANK_TOKEN_HEADER,
    NBU_BASE_URL,
)
from mono_it_tax.config.enums import Currency, Service
from mono_it_tax.config.settings import Settings

pytestmark = pytest.mark.smoke
POLICY = RetryPolicy(attempts=3, backoff_s=2.0)


def test_nbu_usd_known_day() -> None:
    gateway = HttpGateway(httpx.Client(base_url=NBU_BASE_URL), Service.NBU, SystemClock(), POLICY)
    rates = NbuClient(gateway).rates(Currency.USD, date(2026, 1, 1), date(2026, 1, 5))
    assert rates[date(2026, 1, 1)] == Decimal("42.3532")
    assert len(rates) == 5  # weekends included


def test_monobank_client_info_parses() -> None:
    token = Settings().monobank_token.get_secret_value()
    if not token:
        pytest.skip("MONOBANK_TOKEN not set")
    http = httpx.Client(base_url=MONOBANK_BASE_URL, headers={MONOBANK_TOKEN_HEADER: token})
    gateway = HttpGateway(http, Service.MONOBANK, SystemClock(), POLICY, MONOBANK_MIN_INTERVAL_S)
    assert MonobankClient(gateway).client_info().accounts
