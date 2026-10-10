"""A fake Monobank + NBU behind httpx.MockTransport: scenarios exercise the real clients, retry,
throttle and parsing; only the network is replaced."""

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from mono_it_tax.config.constants.api import MONOBANK_PAGE_LIMIT
from mono_it_tax.config.settings import Settings
from mono_it_tax.domain.months import KYIV
from mono_it_tax.startup import App, World, build_app
from tests.support import FakeClock, bank_item, json_response

STATEMENT = re.compile(r"/personal/statement/(?P<acc>[^/]+)/(?P<start>\d+)/(?P<end>\d+)")
MONO_HOST = "api.monobank.ua"
NBU_HOST = "bank.gov.ua"
REPO_RULES = Path(__file__).resolve().parents[2] / "data" / "rules"


def kyiv_ts(year: int, month: int, day: int, hour: int = 12, minute: int = 0) -> int:
    return int(datetime(year, month, day, hour, minute, tzinfo=KYIV).timestamp())


class FakeKeyring:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], str] = {}

    def is_usable(self) -> bool:
        return True

    def get_password(self, service: str, username: str) -> str | None:
        return self.items.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.items[(service, username)] = password


class FakeBank:
    def __init__(self) -> None:
        self.items: dict[str, list[dict[str, Any]]] = {}
        self.accounts: list[dict[str, Any]] = [
            {
                "id": "acc-1",
                "currencyCode": 980,
                "type": "black",
                "maskedPan": ["537541******1111"],
            },
            {"id": "acc-2", "currencyCode": 840, "type": "fop", "iban": "UA00"},
        ]
        self.statement_calls: list[tuple[str, int, int]] = []
        self.client_info_calls = 0
        self.nbu_calls: list[dict[str, str]] = []
        self.nbu_missing_days: set[date] = set()
        self.statement_hook: Callable[[int], httpx.Response | Exception | None] | None = None

    def add(self, account: str, item: dict[str, Any]) -> None:
        self.items.setdefault(account, []).append(item)

    @staticmethod
    def nbu_rate(day: date) -> Decimal:
        return Decimal("40") + Decimal(day.day) / 100

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if request.url.host == NBU_HOST:
            return self._nbu(request)
        if request.url.path == "/personal/client-info":
            self.client_info_calls += 1
            return json_response({"clientId": "c", "accounts": self.accounts})
        match = STATEMENT.fullmatch(request.url.path)
        if match is None:
            return json_response({}, 404)
        account, start, end = match["acc"], int(match["start"]), int(match["end"])
        self.statement_calls.append((account, start, end))
        if self.statement_hook is not None:
            outcome = self.statement_hook(len(self.statement_calls))
            if isinstance(outcome, Exception):
                raise outcome
            if outcome is not None:
                return outcome
        inside = [i for i in self.items.get(account, []) if start <= i["time"] <= end]
        newest_first = sorted(inside, key=lambda i: -i["time"])
        return json_response(newest_first[:MONOBANK_PAGE_LIMIT])

    def _nbu(self, request: httpx.Request) -> httpx.Response:
        params = request.url.params
        self.nbu_calls.append(dict(params))
        first = datetime.strptime(params["start"], "%Y%m%d").replace(tzinfo=UTC).date()
        last = datetime.strptime(params["end"], "%Y%m%d").replace(tzinfo=UTC).date()
        rows = []
        day = first
        while day <= last:
            if day not in self.nbu_missing_days:
                rows.append(
                    {
                        "exchangedate": day.strftime("%d.%m.%Y"),
                        "cc": params["valcode"].upper(),
                        "rate_per_unit": float(self.nbu_rate(day)),
                    }
                )
            day += timedelta(days=1)
        return json_response(rows)


def make_settings(tmp_path: Path, credential: str = "test-credential") -> Settings:
    rules_dir = tmp_path / "data" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    for path in REPO_RULES.glob("*.yaml"):
        (rules_dir / path.name).write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return Settings(monobank_token=credential, data_dir=tmp_path / "data", _env_file=None)


def make_world(tmp_path: Path, bank: FakeBank, clock: FakeClock) -> World:
    return World(
        transport=httpx.MockTransport(bank),
        clock=clock,
        keyring_backend=FakeKeyring(),
        config_dir=tmp_path / "config",
    )


def make_app(
    tmp_path: Path,
    bank: FakeBank,
    clock: FakeClock | None = None,
    credential: str = "test-credential",
    year: int = 2026,
) -> tuple[App, FakeClock]:
    clock = clock or FakeClock()
    settings = make_settings(tmp_path, credential)
    return build_app(settings, year, make_world(tmp_path, bank, clock)), clock


__all__ = ["FakeBank", "bank_item", "kyiv_ts", "make_app"]
