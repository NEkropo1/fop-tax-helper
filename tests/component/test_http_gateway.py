import httpx
import pytest

from mono_it_tax.clients.http import HttpGateway, RetryPolicy
from mono_it_tax.config.enums import Service
from mono_it_tax.errors import (
    ApiChangedError,
    NetworkError,
    RateLimitedError,
    ServiceDownError,
    TokenRejectedError,
)
from tests.support import FakeClock, json_response

ENDPOINT = "/personal/statement/{account}/{start}/{end}"
POLICY = RetryPolicy(attempts=3, backoff_s=2.0)


class Script:
    """Replays a list of responses/exceptions and records the requests."""

    def __init__(self, *steps: httpx.Response | Exception) -> None:
        self.steps = list(steps)
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        step = self.steps.pop(0)
        if isinstance(step, Exception):
            raise step
        return step


def gateway(
    script: Script, service: Service = Service.MONOBANK, interval: float = 0.0
) -> tuple[HttpGateway, FakeClock]:
    clock = FakeClock()
    client = httpx.Client(base_url="https://x.test", transport=httpx.MockTransport(script))
    return HttpGateway(client, service, clock, POLICY, interval), clock


def test_success_returns_parsed_json_and_passes_params() -> None:
    script = Script(json_response([{"a": 1}]))
    gw, _ = gateway(script)
    assert gw.get_json("/p", ENDPOINT, {"q": "1"}) == [{"a": 1}]
    assert script.requests[0].url.params["q"] == "1"


def test_throttle_waits_the_remaining_interval_between_calls() -> None:
    gw, clock = gateway(Script(json_response([]), json_response([])), interval=60.0)
    gw.get_json("/p", ENDPOINT)
    clock.advance(20)
    gw.get_json("/p", ENDPOINT)
    assert clock.slept == [40.0]


def test_first_call_does_not_wait() -> None:
    gw, clock = gateway(Script(json_response([])), interval=60.0)
    gw.get_json("/p", ENDPOINT)
    assert clock.slept == []


def test_failed_attempt_still_advances_the_throttle() -> None:
    gw, clock = gateway(Script(json_response({}, 503), json_response([])), interval=60.0)
    gw.get_json("/p", ENDPOINT)
    assert sum(clock.slept) >= 60.0  # backoff + throttle together respect the bank's limit


def test_timeout_is_retried_then_reported_as_network_error() -> None:
    script = Script(*[httpx.ConnectTimeout("t")] * 3)
    gw, clock = gateway(script)
    with pytest.raises(NetworkError) as exc:
        gw.get_json("/p/secret-account-id", ENDPOINT)
    assert exc.value.params == {"service": "Monobank", "endpoint": ENDPOINT, "attempts": "3"}
    assert "secret-account-id" not in str(exc.value)
    assert len(script.requests) == 3
    assert clock.slept == [2.0, 4.0]  # exponential backoff, no sleep after the last attempt


def test_recovers_after_a_transient_error() -> None:
    gw, _ = gateway(Script(httpx.ReadError("boom"), json_response({"ok": True})))
    assert gw.get_json("/p", ENDPOINT) == {"ok": True}


def test_server_errors_exhaust_into_service_down() -> None:
    script = Script(*[json_response({}, 502)] * 3)
    gw, _ = gateway(script)
    with pytest.raises(ServiceDownError):
        gw.get_json("/p", ENDPOINT)
    assert len(script.requests) == 3


def test_rate_limit_honours_retry_after_then_gives_up() -> None:
    script = Script(*[json_response({}, 429, {"Retry-After": "30"})] * 3)
    gw, clock = gateway(script)
    with pytest.raises(RateLimitedError):
        gw.get_json("/p", ENDPOINT)
    assert clock.slept == [30.0, 30.0]


def test_rate_limit_then_success() -> None:
    gw, clock = gateway(Script(json_response({}, 429, {"Retry-After": "5"}), json_response([1])))
    assert gw.get_json("/p", ENDPOINT) == [1]
    assert clock.slept == [5.0]


@pytest.mark.parametrize("status", [401, 403])
def test_monobank_auth_failure_is_token_rejected_without_retry(status: int) -> None:
    script = Script(json_response({}, status))
    gw, _ = gateway(script)
    with pytest.raises(TokenRejectedError):
        gw.get_json("/p", ENDPOINT)
    assert len(script.requests) == 1


def test_other_4xx_is_api_changed_without_retry() -> None:
    script = Script(json_response({}, 404))
    gw, _ = gateway(script)
    with pytest.raises(ApiChangedError):
        gw.get_json("/p", ENDPOINT)
    assert len(script.requests) == 1


def test_auth_status_from_nbu_is_not_blamed_on_a_token() -> None:
    gw, _ = gateway(Script(json_response({}, 403)), service=Service.NBU)
    with pytest.raises(ApiChangedError):
        gw.get_json("/p", ENDPOINT)


def test_non_json_body_is_api_changed() -> None:
    gw, _ = gateway(Script(httpx.Response(200, content=b"<html>oops</html>")))
    with pytest.raises(ApiChangedError):
        gw.get_json("/p", ENDPOINT)
