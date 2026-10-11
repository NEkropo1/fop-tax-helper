from datetime import UTC, date, datetime
from decimal import Decimal

import httpx
import pytest

from mono_it_tax.clients.http import HttpGateway, RetryPolicy
from mono_it_tax.clients.monobank import MonobankClient
from mono_it_tax.clients.nbu import NbuClient
from mono_it_tax.config.constants.api import (
    MONOBANK_MAX_SPAN_S,
    MONOBANK_PAGE_LIMIT,
    MONOBANK_TOKEN_HEADER,
)
from mono_it_tax.config.enums import Currency, Service
from mono_it_tax.errors import ApiChangedError
from tests.support import USD_CODE, FakeClock, bank_item, json_response

START = datetime(2026, 7, 1, tzinfo=UTC)
END = datetime(2026, 7, 31, tzinfo=UTC)
POLICY = RetryPolicy(attempts=2, backoff_s=1.0)


def mono(handler: httpx.MockTransport) -> MonobankClient:
    client = httpx.Client(
        base_url="https://m.test", transport=handler, headers={MONOBANK_TOKEN_HEADER: "tok"}
    )
    return MonobankClient(HttpGateway(client, Service.MONOBANK, FakeClock(), POLICY, 60.0))


def serving(*pages: object) -> tuple[httpx.MockTransport, list[httpx.Request]]:
    seen: list[httpx.Request] = []
    queue = list(pages)

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return json_response(queue.pop(0))

    return httpx.MockTransport(handler), seen


def test_client_info_parses_accounts_and_sends_the_token_header() -> None:
    transport, seen = serving(
        {
            "clientId": "c1",
            "name": "ignored",
            "accounts": [
                {
                    "id": "a1",
                    "currencyCode": 980,
                    "type": "black",
                    "maskedPan": ["537541******1234"],
                },
                {"id": "a2", "currencyCode": 840, "type": "fop", "iban": "UA00"},
            ],
            "jars": [],
        }
    )
    info = mono(transport).client_info()
    assert [a.id for a in info.accounts] == ["a1", "a2"]
    assert info.accounts[0].masked_pan == ("537541******1234",)
    assert seen[0].headers[MONOBANK_TOKEN_HEADER] == "tok"


def test_client_info_wrong_shape_is_api_changed() -> None:
    transport, _ = serving({"accounts": [{"no_id": 1}]})
    with pytest.raises(ApiChangedError):
        mono(transport).client_info()


def test_statement_keeps_only_incoming_dedupes_and_orders() -> None:
    page = [
        bank_item("b", 200, 500),
        bank_item("a", 100, 300),
        bank_item("out", 150, -999),
        bank_item("a", 100, 300),  # the bank repeated an item
    ]
    transport, _ = serving(page)
    result = mono(transport).statement("acc", Currency.UAH, START, END)
    assert [p.id for p in result.incoming] == ["a", "b"]
    assert result.items_received == 4


def test_unsupported_operation_currency_in_an_outgoing_item_is_ignored() -> None:
    transport, _ = serving([bank_item("o", 1, -5, currency_code=1)])
    assert mono(transport).statement("acc", Currency.UAH, START, END).incoming == ()


def test_payment_amount_is_in_the_account_currency_not_the_operation_currency() -> None:
    """A USD payment credited to a UAH card: `amount` is UAH, the bank's currencyCode says USD."""
    item = bank_item("conv", 1, 150_000, currency_code=USD_CODE, operationAmount=3_600)
    transport, _ = serving([item])
    payment = mono(transport).statement("acc", Currency.UAH, START, END).incoming[0]
    assert payment.currency is Currency.UAH
    assert payment.operation_currency is Currency.USD
    assert payment.operation_amount == 3_600


def test_unsupported_operation_currency_is_kept_in_raw_not_fatal() -> None:
    transport, _ = serving([bank_item("i", 1, 5, currency_code=1)])
    payment = mono(transport).statement("acc", Currency.UAH, START, END).incoming[0]
    assert payment.currency is Currency.UAH
    assert payment.operation_currency is None
    assert payment.raw["currencyCode"] == 1


def test_full_page_is_followed_backwards_in_time() -> None:
    first = [bank_item(f"n{i}", 10_000 - i, 1) for i in range(MONOBANK_PAGE_LIMIT)]
    second = [bank_item(f"m{i}", 5_000 - i, 1) for i in range(3)]
    transport, seen = serving(first, second)
    result = mono(transport).statement("acc", Currency.UAH, START, END)
    assert len(result.incoming) == MONOBANK_PAGE_LIMIT + 3
    assert result.items_received == MONOBANK_PAGE_LIMIT + 3
    oldest_of_first = 10_000 - (MONOBANK_PAGE_LIMIT - 1)
    assert seen[1].url.path.endswith(f"/{oldest_of_first}")  # next page ends at the oldest item


def test_a_full_page_inside_one_second_cannot_be_paged() -> None:
    stuck = [bank_item(f"x{i}", int(END.timestamp()), 1) for i in range(MONOBANK_PAGE_LIMIT)]
    transport, _ = serving(stuck)
    with pytest.raises(ApiChangedError):
        mono(transport).statement("acc", Currency.UAH, START, END)


def test_statement_range_over_the_api_limit_is_a_programming_error() -> None:
    transport, _ = serving()
    too_long = datetime.fromtimestamp(START.timestamp() + MONOBANK_MAX_SPAN_S + 1, UTC)
    with pytest.raises(ValueError, match="exceeds"):
        mono(transport).statement("acc", Currency.UAH, START, too_long)


def test_statement_garbage_is_api_changed() -> None:
    transport, _ = serving({"error": "nope"})
    with pytest.raises(ApiChangedError):
        mono(transport).statement("acc", Currency.UAH, START, END)
    transport, _ = serving([{"id": "x", "time": 1}])  # no amount
    with pytest.raises(ApiChangedError):
        mono(transport).statement("acc", Currency.UAH, START, END)


def nbu(body: object) -> tuple[NbuClient, list[httpx.Request]]:
    transport, seen = serving(body)
    client = httpx.Client(base_url="https://n.test", transport=transport)
    return NbuClient(HttpGateway(client, Service.NBU, FakeClock(), POLICY)), seen


def test_nbu_rates_parsed_with_request_params() -> None:
    body = [
        {"exchangedate": "01.01.2026", "cc": "USD", "rate_per_unit": 42.3532},
        {"exchangedate": "02.01.2026", "cc": "USD", "rate_per_unit": 42.1701},
    ]
    client, seen = nbu(body)
    rates = client.rates(Currency.USD, date(2026, 1, 1), date(2026, 1, 2))
    assert rates == {date(2026, 1, 1): Decimal("42.3532"), date(2026, 1, 2): Decimal("42.1701")}
    params = seen[0].url.params
    assert (params["start"], params["end"], params["valcode"]) == ("20260101", "20260102", "usd")


@pytest.mark.parametrize(
    "body",
    [{"oops": 1}, [{"exchangedate": "2026-01-01", "rate_per_unit": 1}], [{"nodate": 1}]],
)
def test_nbu_garbage_is_api_changed(body: object) -> None:
    client, _ = nbu(body)
    with pytest.raises(ApiChangedError):
        client.rates(Currency.USD, date(2026, 1, 1), date(2026, 1, 2))
