"""One background fetch at a time: progress for the UI, cancellable between requests."""

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import StrEnum

from mono_it_tax.errors import AppError, JobNotFoundError, JobRunningError
from mono_it_tax.services.fetch import FetchOutcome, FetchProgress

log = logging.getLogger(__name__)

Work = Callable[[Callable[[FetchProgress], None], Callable[[], bool]], FetchOutcome]


class JobState(StrEnum):
    RUNNING = "running"
    DONE = "done"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    state: JobState
    done: int
    total: int
    month: str | None
    error: AppError | None  # a typed, user-explainable failure
    internal_error: bool  # anything else: logged, shown as a generic message


class JobRunner:
    """`inline=True` runs the work synchronously (deterministic tests); production uses a thread."""

    def __init__(self, *, inline: bool = False) -> None:
        self._inline = inline
        self._lock = threading.Lock()
        self._jobs: dict[str, JobSnapshot] = {}
        self._cancel: dict[str, threading.Event] = {}

    def start(self, work: Work, total: int) -> JobSnapshot:
        with self._lock:
            if any(j.state is JobState.RUNNING for j in self._jobs.values()):
                raise JobRunningError
            job_id = uuid.uuid4().hex
            self._jobs[job_id] = JobSnapshot(
                job_id, JobState.RUNNING, 0, total, None, None, internal_error=False
            )
            self._cancel[job_id] = threading.Event()
        if self._inline:
            self._run(job_id, work)
        else:
            threading.Thread(target=self._run, args=(job_id, work), daemon=True).start()
        return self.get(job_id)

    def get(self, job_id: str) -> JobSnapshot:
        with self._lock:
            try:
                return self._jobs[job_id]
            except KeyError:
                raise JobNotFoundError from None

    def cancel(self, job_id: str) -> JobSnapshot:
        snapshot = self.get(job_id)
        self._cancel[job_id].set()
        return snapshot

    def _update(self, job_id: str, **changes: object) -> None:
        with self._lock:
            self._jobs[job_id] = replace(self._jobs[job_id], **changes)  # type: ignore[arg-type]

    def _run(self, job_id: str, work: Work) -> None:
        def on_progress(progress: FetchProgress) -> None:
            self._update(job_id, done=progress.done, month=str(progress.task.month))

        try:
            outcome = work(on_progress, self._cancel[job_id].is_set)
        except AppError as error:
            self._update(job_id, state=JobState.FAILED, error=error)
        except Exception:
            log.exception("fetch job %s crashed", job_id)
            self._update(job_id, state=JobState.FAILED, internal_error=True)
        else:
            state = JobState.CANCELLED if outcome.cancelled else JobState.DONE
            self._update(job_id, state=state, done=outcome.completed)
