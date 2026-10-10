"""`uv run mono-it-tax`: start the local server on a free port and open the browser.

The per-launch token travels in the URL fragment (never sent to a server, not logged); the page
reads it and sends it as a header on every API call, so other web pages cannot talk to this app.
"""

import logging
import secrets
import socket
import webbrowser

import uvicorn

from mono_it_tax.api.main import create_app
from mono_it_tax.clock import SystemClock
from mono_it_tax.config.constants.app import LAUNCH_TOKEN_BYTES, LOCAL_HOST, WEB_DIST_RELATIVE
from mono_it_tax.config.settings import PROJECT_ROOT, Settings

UI_NOT_BUILT = (
    "The web UI is not built yet. Once: `npm --prefix web install`, then "
    "`npm --prefix web run build`; then start again."
)
LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
LOG_TIMESTAMP = "%Y%m%d_%H%M%S"


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind((LOCAL_HOST, 0))
        return int(probe.getsockname()[1])


def setup_logging(settings: Settings) -> None:
    log_dir = settings.data_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = SystemClock().now().strftime(LOG_TIMESTAMP)
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        handlers=[logging.FileHandler(log_dir / f"{stamp}_app.log", encoding="utf-8")],
    )
    for noisy in ("httpx", "httpcore"):  # their request lines carry account ids in URL paths
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main() -> None:  # pragma: no cover - starts a server and a browser; exercised by hand
    settings = Settings()
    setup_logging(settings)
    token = secrets.token_urlsafe(LAUNCH_TOKEN_BYTES)
    port = free_port()
    web_dir = PROJECT_ROOT.joinpath(*WEB_DIST_RELATIVE)
    if not web_dir.is_dir():
        print(UI_NOT_BUILT)
    app = create_app(settings, token, web_dir=web_dir)
    url = f"http://{LOCAL_HOST}:{port}/#token={token}"
    print(f"mono-it-tax is running at {url}\nPress Ctrl+C to stop.")
    webbrowser.open(url)
    uvicorn.run(app, host=LOCAL_HOST, port=port, log_level="warning")
