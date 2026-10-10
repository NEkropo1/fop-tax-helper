"""Per-process API state: the built app (or why it failed), handles, jobs and the launch token."""

import hmac
from dataclasses import dataclass

from fastapi import Header

from mono_it_tax.api.handles import AccountHandles
from mono_it_tax.api.jobs import JobRunner
from mono_it_tax.config.constants.app import LAUNCH_TOKEN_HEADER
from mono_it_tax.errors import AppError
from mono_it_tax.startup import App


@dataclass(frozen=True)
class ApiState:
    launch_token: str
    jobs: JobRunner
    app: App | None  # None when preflight failed (see `startup_error`)
    handles: AccountHandles | None
    startup_error: AppError | None

    def ready_app(self) -> App:
        """The app, or the stored startup error (the UI shows its how-to message)."""
        if self.app is None or self.startup_error is not None:
            raise self.startup_error or RuntimeError("app is not built")
        return self.app

    def ready_handles(self) -> AccountHandles:
        if self.handles is None:
            raise self.startup_error or RuntimeError("handles are not built")
        return self.handles

    def token_matches(self, supplied: str | None) -> bool:
        return supplied is not None and hmac.compare_digest(supplied, self.launch_token)


def token_header(
    x_app_token: str | None = Header(default=None, alias=LAUNCH_TOKEN_HEADER),
) -> str | None:
    return x_app_token
