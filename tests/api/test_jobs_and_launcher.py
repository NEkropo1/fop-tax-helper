import threading
from datetime import UTC, datetime

import pytest

from mono_it_tax.api.jobs import JobRunner, JobState
from mono_it_tax.config.settings import Settings
from mono_it_tax.domain.months import Month
from mono_it_tax.errors import JobNotFoundError, JobRunningError, NetworkError
from mono_it_tax.launcher import free_port, setup_logging
from mono_it_tax.services.fetch import FetchOutcome, FetchProgress, FetchTask

TASK = FetchTask(
    "a", Month(2026, 7), datetime(2026, 7, 1, tzinfo=UTC), datetime(2026, 8, 1, tzinfo=UTC)
)


def test_inline_job_reports_progress_and_completion() -> None:
    runner = JobRunner(inline=True)

    def work(on_progress, should_cancel):  # type: ignore[no-untyped-def]
        on_progress(FetchProgress(1, 2, TASK))
        on_progress(FetchProgress(2, 2, TASK))
        return FetchOutcome(2, 2, cancelled=False)

    job = runner.start(work, total=2)
    assert (job.state, job.done, job.month) == (JobState.DONE, 2, "2026-07")


def test_cancelled_and_failed_outcomes() -> None:
    runner = JobRunner(inline=True)
    cancelled = runner.start(lambda *_: FetchOutcome(1, 3, cancelled=True), total=3)
    assert (cancelled.state, cancelled.done) == (JobState.CANCELLED, 1)

    def typed_failure(*_: object) -> FetchOutcome:
        raise NetworkError(service="Monobank", endpoint="/x", attempts=3)

    failed = runner.start(typed_failure, total=1)
    assert failed.state is JobState.FAILED
    assert failed.error is not None
    assert failed.internal_error is False

    def crash(*_: object) -> FetchOutcome:
        raise RuntimeError("bug")

    crashed = runner.start(crash, total=1)
    assert (crashed.state, crashed.internal_error) == (JobState.FAILED, True)


def test_unknown_job() -> None:
    with pytest.raises(JobNotFoundError):
        JobRunner(inline=True).get("nope")


def test_only_one_job_runs_at_a_time_and_cancel_is_honoured() -> None:
    runner = JobRunner()
    started, release = threading.Event(), threading.Event()

    def slow(on_progress, should_cancel):  # type: ignore[no-untyped-def]
        started.set()
        release.wait(timeout=5)
        return FetchOutcome(0, 1, cancelled=should_cancel())

    first = runner.start(slow, total=1)
    assert started.wait(timeout=5)
    with pytest.raises(JobRunningError):
        runner.start(slow, total=1)
    runner.cancel(first.id)
    release.set()
    for _ in range(100):
        if runner.get(first.id).state is not JobState.RUNNING:
            break
        threading.Event().wait(0.02)
    assert runner.get(first.id).state is JobState.CANCELLED


def test_free_port_is_usable() -> None:
    assert 1024 <= free_port() <= 65535


def test_launcher_logging_goes_to_a_file_under_data(tmp_path) -> None:  # type: ignore[no-untyped-def]
    settings = Settings(data_dir=tmp_path, _env_file=None)
    setup_logging(settings)
    assert list((tmp_path / "logs").glob("*_app.log"))
