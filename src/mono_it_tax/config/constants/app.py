"""Application constants: local server, launch token, maintainer contact, static UI location."""

LOCAL_HOST = "127.0.0.1"
ALLOWED_HOSTS = ("127.0.0.1", "localhost")
LAUNCH_TOKEN_HEADER = "X-App-Token"  # noqa: S105  (header name, not a secret)
LAUNCH_TOKEN_BYTES = 32
AUTHOR_LINKEDIN = "https://www.linkedin.com/in/paul-savchuk-ne/"
PACKAGE_NAME = "mono-it-tax"
WEB_DIST_RELATIVE = ("web", "dist")
