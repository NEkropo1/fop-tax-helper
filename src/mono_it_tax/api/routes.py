"""Thin routes: parse the request, call a pipeline/service, map the result. No tax math here."""

from collections.abc import Callable, Sequence
from decimal import Decimal, InvalidOperation
from importlib.metadata import PackageNotFoundError, version

from fastapi import APIRouter, Depends, HTTPException, Request

from mono_it_tax.api.schemas import (
    AccountOut,
    AmountIn,
    DataOut,
    DataYearOut,
    DeclarationIn,
    DeclarationOut,
    ErrorOut,
    EstimateOut,
    JobOut,
    MarkIn,
    MetaOut,
    MonthStateOut,
    PaymentOut,
    PaymentsOut,
    PlannedPaymentOut,
    PlanOut,
    PlanTaskOut,
    ReviewIn,
    RulesOut,
    ScopeIn,
    parse_month,
)
from mono_it_tax.api.state import ApiState, token_header
from mono_it_tax.config.constants.app import AUTHOR_LINKEDIN, PACKAGE_NAME
from mono_it_tax.config.enums import MonthState, Period
from mono_it_tax.config.rules import Rules, available_years
from mono_it_tax.copy.declaration_uk import previous_report_request
from mono_it_tax.copy.errors_uk import INTERNAL_ERROR_TEXT, render_error
from mono_it_tax.domain.account import Account
from mono_it_tax.domain.currency import currency_from_numeric
from mono_it_tax.domain.declaration import PreviousDeclaration
from mono_it_tax.domain.money import mask_pan, minor_to_decimal
from mono_it_tax.domain.months import KYIV, Month, kyiv_date
from mono_it_tax.domain.payment import Payment, is_possible_internal_transfer
from mono_it_tax.domain.periods import MonthsSelection, Selection, previous_period
from mono_it_tax.errors import (
    AppError,
    MonthNotFetchedError,
    UnknownPaymentError,
    UnsupportedCurrencyError,
)
from mono_it_tax.pipelines.fetch import months_to_fetch
from mono_it_tax.services.fetch import FetchOutcome, FetchProgress
from mono_it_tax.services.marking import month_payments, state_of
from mono_it_tax.startup import App

router = APIRouter(prefix="/api")


def get_state(request: Request) -> ApiState:
    state: ApiState = request.app.state.api
    return state


def authorized(
    state: ApiState = Depends(get_state),
    supplied: str | None = Depends(token_header),
) -> ApiState:
    if not state.token_matches(supplied):
        raise HTTPException(status_code=401)
    return state


def error_out(error: AppError, li_link: str) -> ErrorOut:
    return ErrorOut(code=error.code, message=render_error(error, li_link), params=error.params)


def _li_link(state: ApiState) -> str:
    if state.app is not None:
        return state.app.rules.contact.linkedin
    return AUTHOR_LINKEDIN


def _app_version() -> str:
    try:
        return version(PACKAGE_NAME)
    except PackageNotFoundError:
        return "dev"


def _currency_text(account: Account) -> tuple[str, bool]:
    try:
        return currency_from_numeric(account.currency_code).value, True
    except UnsupportedCurrencyError:
        return str(account.currency_code), False


def _month_text(month: Month) -> str:
    return str(month)


def _scope(app: ApiState, scope: ScopeIn) -> tuple[App, Selection, list[str], dict[str, str]]:
    """The app, the domain selection, real account ids, and id -> handle for the output."""
    built = app.ready_app()
    selection = scope.selection.to_domain()
    accounts = built.accounts.accounts(selection.year)
    handles = app.ready_handles()
    ids = [handles.resolve(h, accounts) for h in scope.handles]
    return built, selection, ids, {a.id: handles.of(a.id) for a in accounts}


def _money(minor: int | None) -> str | None:
    return None if minor is None else str(minor_to_decimal(minor))


def payment_out(
    payment: Payment, handle: str, built: App, *, marked: bool, override: Decimal | None
) -> PaymentOut:
    return PaymentOut(
        id=payment.id,
        handle=handle,
        month=_month_text(Month(payment.tax_date.year, payment.tax_date.month)),
        time=payment.time.astimezone(KYIV).isoformat(timespec="minutes"),
        amount=str(minor_to_decimal(payment.amount)),
        currency=payment.currency.value,
        operation_currency=payment.operation_currency.value if payment.operation_currency else None,
        description=payment.description,
        comment=payment.comment,
        counter_name=payment.counter_name,
        counter_edrpou=payment.counter_edrpou,
        counter_iban=payment.counter_iban,
        mcc=payment.mcc,
        original_mcc=payment.original_mcc,
        operation_amount=_money(payment.operation_amount),
        commission_rate=_money(payment.commission_rate),
        cashback_amount=_money(payment.cashback_amount),
        balance=_money(payment.balance),
        hold=payment.hold,
        extra=payment.extra_raw,
        possible_internal_transfer=is_possible_internal_transfer(
            payment, built.rules.internal_transfer
        ),
        marked=marked,
        amount_override=None if override is None else str(override),
    )


def _estimate_out(
    built: App, selection: Selection, ids: Sequence[str], rules: Rules
) -> EstimateOut:
    months = MonthsSelection(selection.months)
    pipeline = built.report_pipeline
    estimate = pipeline.months_estimate(months, ids, rules)
    return EstimateOut(
        income=str(estimate.income_uah),
        single_tax=str(estimate.single_tax),
        military_levy=str(estimate.military_levy),
        esv=str(estimate.esv),
        total=str(estimate.total),
        months=estimate.months,
        text=pipeline.months_report(months, ids, rules),
    )


@router.get("/meta", response_model=MetaOut)
def meta(year: int | None = None, state: ApiState = Depends(authorized)) -> MetaOut:
    error = error_out(state.startup_error, _li_link(state)) if state.startup_error else None
    built = state.app
    years = available_years(built.settings.rules_dir) if built else []
    rules_out: RulesOut | None = None
    if built is not None:
        try:
            rules = built.rules_for(year if year in years else built.rules.year)
            rules_out = RulesOut(
                year=rules.year,
                version=rules.version,
                updated_on=rules.updated_on,
                disclaimer=rules.disclaimer,
                cabinet=rules.links.cabinet,
                tax_account=rules.links.tax_account,
                new_declaration=rules.links.new_declaration,
                declaration_video=rules.links.declaration_video,
                channels=[{"name": c.name, "url": c.url} for c in rules.channels],
                linkedin=rules.contact.linkedin,
            )
        except AppError as exc:
            error = error_out(exc, _li_link(state))
    return MetaOut(
        ready=built is not None and error is None,
        error=error,
        version=_app_version(),
        store_key=built.key_provider.name if built else None,
        years=years,
        current_year=kyiv_date(built.clock.now()).year if built else None,
        rules=rules_out,
    )


@router.get("/accounts", response_model=list[AccountOut])
def accounts(
    year: int, refresh: bool = False, state: ApiState = Depends(authorized)
) -> list[AccountOut]:
    built = state.ready_app()
    handles = state.ready_handles()
    out = []
    for account in built.accounts.accounts(year, refresh=refresh):
        currency, supported = _currency_text(account)
        out.append(
            AccountOut(
                handle=handles.of(account.id),
                type=account.type,
                currency=currency,
                masked_pans=[mask_pan(pan) for pan in account.masked_pan],
                selectable=supported,
            )
        )
    return out


@router.post("/plan", response_model=PlanOut)
def plan(scope: ScopeIn, state: ApiState = Depends(authorized)) -> PlanOut:
    built, selection, ids, to_handle = _scope(state, scope)
    fetch_plan = built.fetch_pipeline.prepare(selection, ids, with_history=scope.with_history)
    return PlanOut(
        requests=len(fetch_plan.tasks),
        eta_seconds=fetch_plan.eta_seconds,
        tasks=[
            PlanTaskOut(handle=to_handle[t.account_id], month=str(t.month))
            for t in fetch_plan.tasks
        ],
    )


def _job_out(state: ApiState, job_id: str) -> JobOut:
    job = state.jobs.get(job_id)
    error = error_out(job.error, _li_link(state)) if job.error else None
    if job.internal_error:
        error = ErrorOut(code="internal", message=INTERNAL_ERROR_TEXT)
    return JobOut(
        id=job.id,
        state=job.state,
        done=job.done,
        total=job.total,
        month=job.month,
        error=error,
    )


@router.post("/fetch", response_model=JobOut)
def start_fetch(scope: ScopeIn, state: ApiState = Depends(authorized)) -> JobOut:
    built, selection, ids, _ = _scope(state, scope)
    built.accounts.choose(selection.year, ids)
    fetch_plan = built.fetch_pipeline.prepare(selection, ids, with_history=scope.with_history)

    def run(
        on_progress: Callable[[FetchProgress], None], should_cancel: Callable[[], bool]
    ) -> FetchOutcome:
        return built.fetch_pipeline.execute(selection, fetch_plan, on_progress, should_cancel)

    job = state.jobs.start(run, total=len(fetch_plan.tasks))
    return _job_out(state, job.id)


@router.get("/jobs/{job_id}", response_model=JobOut)
def job(job_id: str, state: ApiState = Depends(authorized)) -> JobOut:
    return _job_out(state, job_id)


@router.post("/jobs/{job_id}/cancel", response_model=JobOut)
def cancel_job(job_id: str, state: ApiState = Depends(authorized)) -> JobOut:
    state.jobs.cancel(job_id)
    return _job_out(state, job_id)


def _month_states(
    built: App, year: int, ids: Sequence[str], months: Sequence[Month], to_handle: dict[str, str]
) -> list[MonthStateOut]:
    doc = built.store.load(year)
    out = []
    for account_id in ids:
        for month in months:
            listed = month_payments(doc, account_id, month)
            out.append(
                MonthStateOut(
                    handle=to_handle[account_id],
                    month=str(month),
                    state=state_of(doc, account_id, month),
                    payments=len(listed),
                    marked=sum(1 for p in listed if p.id in doc.marks),
                )
            )
    return out


@router.post("/payments", response_model=PaymentsOut)
def payments(scope: ScopeIn, state: ApiState = Depends(authorized)) -> PaymentsOut:
    built, selection, ids, to_handle = _scope(state, scope)
    months = months_to_fetch(selection, with_history=scope.with_history)
    doc = built.store.load(selection.year)
    listed: list[Payment] = []
    for account_id in ids:
        for month in months:
            listed.extend(month_payments(doc, account_id, month))
    listed.sort(key=lambda p: (p.time, p.id))
    out = [
        payment_out(
            p,
            to_handle[p.account_id],
            built,
            marked=p.id in doc.marks,
            override=doc.marks[p.id].amount_override if p.id in doc.marks else None,
        )
        for p in listed
    ]
    return PaymentsOut(
        payments=out, months=_month_states(built, selection.year, ids, months, to_handle)
    )


@router.post("/marks")
def marks(body: MarkIn, state: ApiState = Depends(authorized)) -> dict[str, int]:
    built = state.ready_app()
    known = built.store.load(body.year).payments
    if any(pid not in known for pid in body.payment_ids):
        raise UnknownPaymentError
    if body.marked:
        built.marking.mark(body.year, body.payment_ids)
    else:
        built.marking.unmark(body.year, body.payment_ids)
    return {"changed": len(body.payment_ids)}


@router.post("/marks/amount")
def marks_amount(body: AmountIn, state: ApiState = Depends(authorized)) -> dict[str, str | None]:
    built = state.ready_app()
    if body.payment_id not in built.store.load(body.year).marks:
        raise UnknownPaymentError
    try:
        amount = None if body.amount is None else Decimal(body.amount)
    except InvalidOperation as exc:
        raise HTTPException(status_code=422) from exc
    try:
        built.marking.set_amount(body.year, body.payment_id, amount)
    except ValueError as exc:  # not positive
        raise HTTPException(status_code=422) from exc
    return {"amount": None if amount is None else str(amount)}


@router.post("/review", response_model=list[MonthStateOut])
def review(body: ReviewIn, state: ApiState = Depends(authorized)) -> list[MonthStateOut]:
    built = state.ready_app()
    accounts_ = built.accounts.accounts(body.year)
    handles = state.ready_handles()
    ids = [handles.resolve(h, accounts_) for h in body.handles]
    months = [parse_month(m) for m in body.months]
    for account_id in ids:
        for month in months:
            current = state_of(built.store.load(body.year), account_id, month)
            if current in {MonthState.NOT_FETCHED, MonthState.PARTIAL}:
                raise MonthNotFetchedError(month=month)
            built.marking.review_month(body.year, account_id, month)
    return _month_states(built, body.year, ids, months, {a.id: handles.of(a.id) for a in accounts_})


@router.post("/review/cancel", response_model=list[MonthStateOut])
def cancel_review(body: ReviewIn, state: ApiState = Depends(authorized)) -> list[MonthStateOut]:
    """Reopen confirmed months so their marks can be changed again."""
    built = state.ready_app()
    accounts_ = built.accounts.accounts(body.year)
    handles = state.ready_handles()
    ids = [handles.resolve(h, accounts_) for h in body.handles]
    months = [parse_month(m) for m in body.months]
    for account_id in ids:
        for month in months:
            built.marking.unreview_month(body.year, account_id, month)
    return _month_states(built, body.year, ids, months, {a.id: handles.of(a.id) for a in accounts_})


@router.post("/report/info", response_model=EstimateOut)
def report_info(scope: ScopeIn, state: ApiState = Depends(authorized)) -> EstimateOut:
    built, selection, ids, _ = _scope(state, scope)
    return _estimate_out(built, selection, ids, built.rules_for(selection.year))


def _previous(body: DeclarationIn) -> PreviousDeclaration | None:
    typed = body.previous
    before = previous_period(body.period)
    if typed is None or before is None:
        return None
    try:
        return PreviousDeclaration(
            before,
            Decimal(typed.income),
            Decimal(typed.row_07),
            Decimal(typed.row_12),
            Decimal(typed.row_23),
        )
    except InvalidOperation as exc:
        raise HTTPException(status_code=422) from exc


@router.post("/report/declaration", response_model=DeclarationOut)
def report_declaration(
    body: DeclarationIn, state: ApiState = Depends(authorized)
) -> DeclarationOut:
    built = state.ready_app()
    accounts_ = built.accounts.accounts(body.year)
    handles = state.ready_handles()
    ids = [handles.resolve(h, accounts_) for h in body.handles]
    rules = built.rules_for(body.year)
    help_ = built.report_pipeline.declaration_help(
        body.year, body.period, ids, rules, _previous(body)
    )
    rows = help_.rows
    return DeclarationOut(
        text=help_.text,
        preliminary=help_.preliminary,
        declaration_due=help_.plan.declaration_due,
        payments=[
            PlannedPaymentOut(
                tax=p.tax.value, amount=str(p.amount), due=p.due, budget_code=p.budget_code
            )
            for p in help_.plan.payments
        ],
        rows={
            "income": str(rows.income),
            "tax_at_rate": str(rows.tax_at_rate),
            "row_12": str(rows.row_12),
            "row_13": str(rows.row_13),
            "row_14": str(rows.row_14),
            "row_23": str(rows.row_23),
            "row_24": str(rows.row_24),
            "row_25": str(rows.row_25),
        },
    )


@router.get("/declaration/previous-request")
def previous_request(
    year: int, period: Period, state: ApiState = Depends(authorized)
) -> dict[str, str]:
    """Where in the cabinet to find the previous declaration and which rows to copy."""
    rules = state.ready_app().rules_for(year)
    return {"text": previous_report_request(previous_period(period), year, rules)}


@router.get("/data", response_model=DataOut)
def data(state: ApiState = Depends(authorized)) -> DataOut:
    built = state.ready_app()
    return DataOut(
        folder=str(built.store.directory),
        years=[
            DataYearOut(year=y, bytes=built.store.path(y).stat().st_size)
            for y in built.store.years()
        ],
        key_storage=built.key_provider.name,
    )


@router.delete("/data/{year}")
def delete_year(
    year: int, confirm: bool = False, state: ApiState = Depends(authorized)
) -> dict[str, int]:
    if not confirm:
        raise HTTPException(status_code=400)
    state.ready_app().store.delete_year(year)
    return {"deleted": year}


@router.delete("/data")
def delete_all(confirm: bool = False, state: ApiState = Depends(authorized)) -> dict[str, bool]:
    if not confirm:
        raise HTTPException(status_code=400)
    state.ready_app().store.delete_all()
    return {"deleted_all": True}
