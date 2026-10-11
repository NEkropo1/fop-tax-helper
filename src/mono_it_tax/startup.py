"""Composition root: the only place that builds clients, store, clock and services from settings.

Preflight fails fast (missing token, unreadable rules, unavailable store key) so the user sees the
how-to message at launch, not in the middle of a 10-minute fetch.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import httpx
from platformdirs import user_config_dir

from mono_it_tax.clients.http import HttpGateway, RetryPolicy
from mono_it_tax.clients.monobank import MonobankClient
from mono_it_tax.clients.nbu import NbuClient
from mono_it_tax.clock import Clock, SystemClock
from mono_it_tax.config.constants.api import (
    MONOBANK_BASE_URL,
    MONOBANK_MIN_INTERVAL_S,
    MONOBANK_TOKEN_HEADER,
    NBU_BASE_URL,
)
from mono_it_tax.config.constants.store import APP_NAME, STORE_DIR_NAME
from mono_it_tax.config.enums import Service
from mono_it_tax.config.rules import Rules, available_years, load_rules
from mono_it_tax.config.settings import Settings
from mono_it_tax.errors import ConfigTokenMissingError
from mono_it_tax.pipelines.fetch import FetchPipeline
from mono_it_tax.pipelines.report import ReportPipeline
from mono_it_tax.services.accounts import AccountService
from mono_it_tax.services.fetch import FetchService
from mono_it_tax.services.marking import MarkingService
from mono_it_tax.services.rates import RatesService
from mono_it_tax.services.reports import ReportService
from mono_it_tax.store.keyring_backend import SystemKeyring
from mono_it_tax.store.keys import KeyringBackend, StoreKeyProvider, select_key_provider
from mono_it_tax.store.year_store import YearStore


@dataclass(frozen=True)
class App:
    settings: Settings
    rules: Rules  # rules of the year the app was built for
    rules_for: Callable[[int], Rules]  # rules of exactly this year (cached); raises a config error
    rules_or_latest: Callable[
        [int], Rules
    ]  # same, but the latest rules file when the year has none
    clock: Clock
    key_provider: StoreKeyProvider
    store: YearStore
    accounts: AccountService
    marking: MarkingService
    fetch_pipeline: FetchPipeline
    report_pipeline: ReportPipeline


@dataclass(frozen=True)
class World:
    """The injected outside world; defaults are the real one (tests pass fakes)."""

    transport: httpx.BaseTransport | None = None
    clock: Clock | None = None
    keyring_backend: KeyringBackend | None = None
    config_dir: Path | None = None


def _cached_rules(rules_dir: Path) -> Callable[[int], Rules]:
    cache: dict[int, Rules] = {}

    def rules_for(year: int) -> Rules:
        if year not in cache:
            cache[year] = load_rules(rules_dir, year)
        return cache[year]

    return rules_for


def _rules_or_latest(rules_dir: Path, rules_for: Callable[[int], Rules]) -> Callable[[int], Rules]:
    """The user's choice, not ours: a year without a rules file is calculated with the latest file
    (relabelled to the requested year so the declaration maths accepts it). The UI warns loudly."""

    def resolve(year: int) -> Rules:
        years = available_years(rules_dir)
        if year in years or not years:
            return rules_for(year)  # a real file, or the config error when there is none at all
        return rules_for(years[-1]).model_copy(update={"year": year})

    return resolve


def build_app(settings: Settings, year: int, world: World = World()) -> App:  # noqa: B008
    """Build everything for `year` (frozen World: safe default)."""
    token = settings.monobank_token.get_secret_value().strip()
    if not token:
        raise ConfigTokenMissingError
    rules_for = _cached_rules(settings.rules_dir)
    rules = rules_for(year)
    clock = world.clock or SystemClock()
    key_provider = select_key_provider(
        settings.key_storage,
        world.config_dir or Path(user_config_dir(APP_NAME)),
        world.keyring_backend or SystemKeyring(),
    )
    key_provider.get_or_create_key()  # fail now, not mid-fetch
    store = YearStore(settings.data_dir / STORE_DIR_NAME, key_provider)

    policy = RetryPolicy(settings.retry_attempts, settings.retry_backoff_s)
    mono_http = httpx.Client(
        base_url=MONOBANK_BASE_URL,
        headers={MONOBANK_TOKEN_HEADER: token},
        timeout=settings.http_timeout_s,
        transport=world.transport,
    )
    nbu_http = httpx.Client(
        base_url=NBU_BASE_URL, timeout=settings.http_timeout_s, transport=world.transport
    )
    monobank = MonobankClient(
        HttpGateway(mono_http, Service.MONOBANK, clock, policy, MONOBANK_MIN_INTERVAL_S)
    )
    nbu = NbuClient(HttpGateway(nbu_http, Service.NBU, clock, policy))

    accounts = AccountService(monobank, store)
    rates = RatesService(nbu, store)
    reports = ReportService(store, clock)
    return App(
        settings=settings,
        rules=rules,
        rules_for=rules_for,
        rules_or_latest=_rules_or_latest(settings.rules_dir, rules_for),
        clock=clock,
        key_provider=key_provider,
        store=store,
        accounts=accounts,
        marking=MarkingService(store, clock),
        fetch_pipeline=FetchPipeline(FetchService(monobank, accounts, store, clock), store),
        report_pipeline=ReportPipeline(reports, rates, clock),
    )
