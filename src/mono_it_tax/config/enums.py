"""Closed sets of values. Compare against members, never bare literals."""

from enum import IntEnum, StrEnum


class Currency(StrEnum):
    UAH = "UAH"
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    PLN = "PLN"


class Service(StrEnum):
    """External services named in errors (value = what the user sees)."""

    MONOBANK = "Monobank"
    NBU = "НБУ"


class Period(StrEnum):
    """Cumulative tax reporting periods of one year."""

    Q1 = "Q1"
    H1 = "H1"
    M9 = "M9"
    Y = "Y"


class Tax(StrEnum):
    ESV = "esv"
    SINGLE_TAX = "single_tax"
    MILITARY_LEVY = "military_levy"


class Scope(StrEnum):
    """What a fetch request kept. A future BOTH never satisfies old INCOMING_ONLY records."""

    INCOMING_ONLY = "incoming_only"


class Coverage(StrEnum):
    NONE = "none"
    PARTIAL = "partial"
    FULL = "full"


class MonthState(StrEnum):
    NOT_FETCHED = "not_fetched"
    PARTIAL = "partial"
    FETCHED = "fetched"
    REVIEWED = "reviewed"


class MarkSource(StrEnum):
    """Where a previous-declaration value came from; MANUAL (actually filed) wins over COMPUTED."""

    MANUAL = "manual"
    COMPUTED = "computed"


class KeyStorage(StrEnum):
    AUTO = "auto"
    KEYRING = "keyring"
    FILE = "file"


class Weekday(IntEnum):
    MONDAY = 0
    SATURDAY = 5
    SUNDAY = 6


class ErrorCode(StrEnum):
    NETWORK = "network"
    SERVICE_DOWN = "service_down"
    TOKEN_REJECTED = "token_rejected"  # noqa: S105  (error code name, not a password)
    RATE_LIMITED = "rate_limited"
    API_CHANGED = "api_changed"
    RATE_MISSING = "rate_missing"
    UNSUPPORTED_CURRENCY = "unsupported_currency"
    STORE_UNREADABLE = "store_unreadable"
    STORE_WRITE_FAILED = "store_write_failed"
    CONFIG_TOKEN_MISSING = "config_token_missing"  # noqa: S105  (error code name)
    CONFIG_RULES_MISSING = "config_rules_missing"
    CONFIG_RULES_INVALID = "config_rules_invalid"
    CONFIG_KEY_UNAVAILABLE = "config_key_unavailable"
    MONTHS_NOT_REVIEWED = "months_not_reviewed"
    UNKNOWN_ACCOUNT = "unknown_account"
    UNKNOWN_PAYMENT = "unknown_payment"
    MONTH_NOT_FETCHED = "month_not_fetched"
    JOB_NOT_FOUND = "job_not_found"
    JOB_RUNNING = "job_running"
    SELECTION_EMPTY = "selection_empty"
    SELECTION_MULTI_YEAR = "selection_multi_year"
    DECL_PREVIOUS_REQUIRED = "decl_previous_required"
    DECL_PREVIOUS_FORBIDDEN = "decl_previous_forbidden"
    DECL_PREVIOUS_NOT_ADJACENT = "decl_previous_not_adjacent"
    DECL_ROW07_NOT_ZERO = "decl_row07_not_zero"
    DECL_ROW_MISMATCH = "decl_row_mismatch"
    DECL_NEGATIVE = "decl_negative"
    DECL_INCOME_OVER_LIMIT = "decl_income_over_limit"
    DECL_RULES_YEAR = "decl_rules_year"
