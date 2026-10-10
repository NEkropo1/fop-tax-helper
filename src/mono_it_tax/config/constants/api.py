"""Facts about the external APIs (official docs: https://api.monobank.ua/docs/, bank.gov.ua)."""

MONOBANK_BASE_URL = "https://api.monobank.ua"
MONOBANK_TOKEN_HEADER = "X-Token"  # noqa: S105  (header name, not a secret)
MONOBANK_CLIENT_INFO_PATH = "/personal/client-info"
# The template (ids unfilled) is also the only form allowed in logs and error texts.
MONOBANK_STATEMENT_PATH = "/personal/statement/{account}/{start}/{end}"
MONOBANK_MIN_INTERVAL_S = 60.0  # 1 request / 60 s per token, shared by all personal endpoints
MONOBANK_MAX_SPAN_S = 2_682_000  # "31 доба + 1 година"
MONOBANK_PAGE_LIMIT = 500  # items per statement response (community docs; verify on busy months)

NBU_BASE_URL = "https://bank.gov.ua"
NBU_RANGE_PATH = "/NBU_Exchange/exchange_site"
NBU_RANGE_PARAMS = {"sort": "exchangedate", "order": "asc", "json": ""}
NBU_DATE_PARAM_FORMAT = "%Y%m%d"
NBU_DATE_RESPONSE_FORMAT = "%d.%m.%Y"

HTTP_TOO_MANY_REQUESTS = 429
HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403
HTTP_SERVER_ERROR_MIN = 500
HTTP_RETRY_AFTER_HEADER = "Retry-After"
RETRY_BACKOFF_FACTOR = 2.0
