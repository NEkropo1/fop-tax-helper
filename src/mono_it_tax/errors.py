"""One error hierarchy. Every error has a code and structured params; the user-facing text is a
catalog lookup (`copy/errors_uk.py`), never an f-string at the raise site. Params must be safe to
show: no tokens, ids, IBANs or full PANs."""

from typing import ClassVar

from mono_it_tax.config.enums import ErrorCode


class AppError(Exception):
    code: ClassVar[ErrorCode]
    PARAMS: ClassVar[tuple[str, ...]] = ()

    def __init__(self, **params: object) -> None:
        if set(params) != set(self.PARAMS):
            raise TypeError(
                f"{type(self).__name__} needs exactly {self.PARAMS}, got {tuple(params)}"
            )
        self.params = {key: str(value) for key, value in params.items()}
        super().__init__(f"{self.code}: {self.params}")


class NetworkError(AppError):
    code = ErrorCode.NETWORK
    PARAMS = ("service", "endpoint", "attempts")


class ServiceDownError(AppError):
    code = ErrorCode.SERVICE_DOWN
    PARAMS = ("service", "endpoint", "attempts")


class TokenRejectedError(AppError):
    code = ErrorCode.TOKEN_REJECTED
    PARAMS = ("service",)


class RateLimitedError(AppError):
    code = ErrorCode.RATE_LIMITED
    PARAMS = ("service", "endpoint", "attempts")


class ApiChangedError(AppError):
    code = ErrorCode.API_CHANGED
    PARAMS = ("service", "endpoint")


class RateMissingError(AppError):
    code = ErrorCode.RATE_MISSING
    PARAMS = ("currency", "date")


class UnsupportedCurrencyError(AppError):
    code = ErrorCode.UNSUPPORTED_CURRENCY
    PARAMS = ("code",)


class StoreUnreadableError(AppError):
    code = ErrorCode.STORE_UNREADABLE
    PARAMS = ("path",)


class StoreWriteError(AppError):
    code = ErrorCode.STORE_WRITE_FAILED
    PARAMS = ("path",)


class ConfigTokenMissingError(AppError):
    code = ErrorCode.CONFIG_TOKEN_MISSING


class ConfigRulesMissingError(AppError):
    code = ErrorCode.CONFIG_RULES_MISSING
    PARAMS = ("path",)


class ConfigRulesInvalidError(AppError):
    code = ErrorCode.CONFIG_RULES_INVALID
    PARAMS = ("path", "detail")


class ConfigKeyUnavailableError(AppError):
    code = ErrorCode.CONFIG_KEY_UNAVAILABLE
    PARAMS = ("detail",)


class MonthsNotReviewedError(AppError):
    code = ErrorCode.MONTHS_NOT_REVIEWED
    PARAMS = ("months",)


class UnknownAccountError(AppError):
    code = ErrorCode.UNKNOWN_ACCOUNT


class UnknownPaymentError(AppError):
    code = ErrorCode.UNKNOWN_PAYMENT


class MonthNotFetchedError(AppError):
    code = ErrorCode.MONTH_NOT_FETCHED
    PARAMS = ("month",)


class JobNotFoundError(AppError):
    code = ErrorCode.JOB_NOT_FOUND


class JobRunningError(AppError):
    code = ErrorCode.JOB_RUNNING


class SelectionEmptyError(AppError):
    code = ErrorCode.SELECTION_EMPTY


class SelectionMultiYearError(AppError):
    code = ErrorCode.SELECTION_MULTI_YEAR


class DeclPreviousRequiredError(AppError):
    code = ErrorCode.DECL_PREVIOUS_REQUIRED
    PARAMS = ("period", "previous")


class DeclPreviousForbiddenError(AppError):
    code = ErrorCode.DECL_PREVIOUS_FORBIDDEN
    PARAMS = ("period",)


class DeclPreviousNotAdjacentError(AppError):
    code = ErrorCode.DECL_PREVIOUS_NOT_ADJACENT
    PARAMS = ("expected", "got")


class DeclRow07NotZeroError(AppError):
    code = ErrorCode.DECL_ROW07_NOT_ZERO
    PARAMS = ("row",)


class DeclRowMismatchError(AppError):
    code = ErrorCode.DECL_ROW_MISMATCH
    PARAMS = ("row", "typed", "expected")


class DeclNegativeError(AppError):
    code = ErrorCode.DECL_NEGATIVE
    PARAMS = ("what",)


class DeclIncomeOverLimitError(AppError):
    code = ErrorCode.DECL_INCOME_OVER_LIMIT
    PARAMS = ("income", "limit")


class DeclRulesYearError(AppError):
    code = ErrorCode.DECL_RULES_YEAR
    PARAMS = ("rules_year", "year")
