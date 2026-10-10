"""FastAPI application factory: auth, host check, error mapping, static UI."""

import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware

from mono_it_tax.api.handles import AccountHandles
from mono_it_tax.api.jobs import JobRunner
from mono_it_tax.api.routes import error_out, router
from mono_it_tax.api.schemas import ErrorOut
from mono_it_tax.api.state import ApiState
from mono_it_tax.config.constants.app import ALLOWED_HOSTS, AUTHOR_LINKEDIN
from mono_it_tax.config.enums import ErrorCode
from mono_it_tax.config.rules import available_years
from mono_it_tax.config.settings import Settings
from mono_it_tax.copy.errors_uk import INTERNAL_ERROR_TEXT
from mono_it_tax.errors import AppError, ConfigRulesMissingError
from mono_it_tax.startup import App, World, build_app

log = logging.getLogger(__name__)

STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.NETWORK: 502,
    ErrorCode.SERVICE_DOWN: 502,
    ErrorCode.TOKEN_REJECTED: 502,  # the bank's token, not the app's: never 401
    ErrorCode.API_CHANGED: 502,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.STORE_UNREADABLE: 409,
    ErrorCode.CONFIG_TOKEN_MISSING: 503,
    ErrorCode.CONFIG_RULES_MISSING: 503,
    ErrorCode.CONFIG_RULES_INVALID: 503,
    ErrorCode.CONFIG_KEY_UNAVAILABLE: 503,
    ErrorCode.UNKNOWN_ACCOUNT: 404,
    ErrorCode.UNKNOWN_PAYMENT: 404,
    ErrorCode.JOB_NOT_FOUND: 404,
    ErrorCode.JOB_RUNNING: 409,
    ErrorCode.MONTHS_NOT_REVIEWED: 409,
    ErrorCode.MONTH_NOT_FETCHED: 409,
}
DEFAULT_ERROR_STATUS = 422  # input the user can correct (selection, declaration rows, rates)


def _build_state(
    settings: Settings, launch_token: str, world: World, *, inline_jobs: bool
) -> ApiState:
    jobs = JobRunner(inline=inline_jobs)
    try:
        years = available_years(settings.rules_dir)
        if not years:
            raise ConfigRulesMissingError(path=settings.rules_dir)
        built: App = build_app(settings, years[-1], world)
        handles = AccountHandles(built.key_provider.get_or_create_key())
    except AppError as error:
        log.exception("startup preflight failed: %s", error.code)
        return ApiState(launch_token, jobs, None, None, error)
    return ApiState(launch_token, jobs, built, handles, None)


def create_app(
    settings: Settings,
    launch_token: str,
    world: World | None = None,
    web_dir: Path | None = None,
    *,
    inline_jobs: bool = False,
) -> FastAPI:
    api = FastAPI(title="mono-it-tax", docs_url=None, redoc_url=None, openapi_url=None)
    api.state.api = _build_state(settings, launch_token, world or World(), inline_jobs=inline_jobs)
    api.add_middleware(TrustedHostMiddleware, allowed_hosts=list(ALLOWED_HOSTS))

    @api.exception_handler(AppError)
    def app_error(request: Request, error: AppError) -> JSONResponse:
        state: ApiState = request.app.state.api
        li_link = state.app.rules.contact.linkedin if state.app else AUTHOR_LINKEDIN
        status = STATUS_BY_CODE.get(error.code, DEFAULT_ERROR_STATUS)
        return JSONResponse(error_out(error, li_link).model_dump(mode="json"), status_code=status)

    @api.exception_handler(Exception)
    def unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled error on %s", request.url.path, exc_info=exc)
        body = ErrorOut(code="internal", message=INTERNAL_ERROR_TEXT)
        return JSONResponse(body.model_dump(mode="json"), status_code=500)

    api.include_router(router)
    if web_dir is not None and web_dir.is_dir():
        api.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return api
