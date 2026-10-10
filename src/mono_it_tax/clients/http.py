"""The one place that talks HTTP: throttle, retry with backoff, error mapping.

Policy: retry connect/read timeouts, connection errors and 5xx; honour 429 Retry-After; never retry
other 4xx. Attempts are bounded; every wait goes through the injected Clock. A failed attempt still
advances the throttle clock (a failed call counts for the bank too).
"""

import logging
from dataclasses import dataclass
from enum import StrEnum

import httpx

from mono_it_tax.clock import Clock
from mono_it_tax.config.constants.api import (
    HTTP_FORBIDDEN,
    HTTP_RETRY_AFTER_HEADER,
    HTTP_SERVER_ERROR_MIN,
    HTTP_TOO_MANY_REQUESTS,
    HTTP_UNAUTHORIZED,
    RETRY_BACKOFF_FACTOR,
)
from mono_it_tax.config.enums import Service
from mono_it_tax.errors import (
    ApiChangedError,
    NetworkError,
    RateLimitedError,
    ServiceDownError,
    TokenRejectedError,
)

log = logging.getLogger(__name__)

_TRANSPORT_ERRORS = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class _Failure(StrEnum):
    """Why the last attempt failed."""

    NETWORK = "network"
    SERVER = "server"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int
    backoff_s: float


class HttpGateway:
    def __init__(
        self,
        client: httpx.Client,
        service: Service,
        clock: Clock,
        policy: RetryPolicy,
        min_interval_s: float = 0.0,
    ) -> None:
        self._client = client
        self._service = service
        self._clock = clock
        self._policy = policy
        self._min_interval_s = min_interval_s
        self._last_attempt: float | None = None

    def get_json(self, path: str, endpoint: str, params: dict[str, str] | None = None) -> object:
        """GET `path`, return parsed JSON. `endpoint` is the id-free template for logs/errors."""
        last_failure: _Failure | None = None
        for attempt in range(1, self._policy.attempts + 1):
            self._throttle()
            try:
                response = self._client.get(path, params=params)
            except _TRANSPORT_ERRORS as exc:
                self._mark_attempt()
                log.debug(
                    "%s %s attempt %d: transport error %s",
                    self._service,
                    endpoint,
                    attempt,
                    type(exc).__name__,
                )
                last_failure = _Failure.NETWORK
                self._backoff(attempt)
                continue
            self._mark_attempt()
            log.debug(
                "%s %s attempt %d: HTTP %d", self._service, endpoint, attempt, response.status_code
            )
            outcome = self._classify(response, endpoint)
            if outcome is None:
                return self._json(response, endpoint)
            last_failure = outcome
            self._wait_after(outcome, response, attempt)
        raise self._final_error(last_failure, endpoint)

    def _classify(self, response: httpx.Response, endpoint: str) -> _Failure | None:
        status = response.status_code
        if status == HTTP_TOO_MANY_REQUESTS:
            return _Failure.RATE_LIMITED
        if status >= HTTP_SERVER_ERROR_MIN:
            return _Failure.SERVER
        if status in {HTTP_UNAUTHORIZED, HTTP_FORBIDDEN} and self._service is Service.MONOBANK:
            raise TokenRejectedError(service=self._service.value)
        if status >= httpx.codes.BAD_REQUEST:
            raise ApiChangedError(service=self._service.value, endpoint=endpoint)
        return None

    def _json(self, response: httpx.Response, endpoint: str) -> object:
        try:
            return response.json()
        except ValueError as exc:
            raise ApiChangedError(service=self._service.value, endpoint=endpoint) from exc

    def _throttle(self) -> None:
        if self._last_attempt is None or self._min_interval_s <= 0:
            return
        wait = self._min_interval_s - (self._clock.monotonic() - self._last_attempt)
        if wait > 0:
            self._clock.sleep(wait)

    def _mark_attempt(self) -> None:
        self._last_attempt = self._clock.monotonic()

    def _backoff(self, attempt: int) -> None:
        if attempt < self._policy.attempts:
            self._clock.sleep(self._policy.backoff_s * RETRY_BACKOFF_FACTOR ** (attempt - 1))

    def _wait_after(self, failure: _Failure, response: httpx.Response, attempt: int) -> None:
        if failure is _Failure.RATE_LIMITED:
            retry_after = response.headers.get(HTTP_RETRY_AFTER_HEADER, "")
            if retry_after.isdigit() and attempt < self._policy.attempts:
                self._clock.sleep(float(retry_after))
            return  # the throttle (min interval) covers the rest before the next attempt
        self._backoff(attempt)

    def _final_error(self, failure: _Failure | None, endpoint: str) -> Exception:
        params = {
            "service": self._service.value,
            "endpoint": endpoint,
            "attempts": self._policy.attempts,
        }
        if failure is _Failure.RATE_LIMITED:
            return RateLimitedError(**params)
        if failure is _Failure.SERVER:
            return ServiceDownError(**params)
        return NetworkError(**params)
