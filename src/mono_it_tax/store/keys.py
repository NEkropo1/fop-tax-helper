"""Where the store encryption key lives. Works on any OS: OS keyring when a real backend exists,
otherwise an owner-only key file in the per-user config directory (never inside `data/`).

Protects the data against copying the files (backup, cloud sync, shared `data/`), not against
someone already logged in as the user.
"""

import logging
import os
from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet

from mono_it_tax.config.constants.store import (
    KEY_FILE_NAME,
    KEY_FILE_POSIX_MODE,
    KEYRING_SERVICE,
    KEYRING_USERNAME,
)
from mono_it_tax.config.enums import KeyStorage
from mono_it_tax.errors import ConfigKeyUnavailableError

log = logging.getLogger(__name__)


class StoreKeyProvider(Protocol):
    @property
    def name(self) -> str: ...

    def get_or_create_key(self) -> bytes: ...


class KeyringBackend(Protocol):
    """The slice of the `keyring` package we use (injected so tests need no real keyring)."""

    def is_usable(self) -> bool: ...

    def get_password(self, service: str, username: str) -> str | None: ...

    def set_password(self, service: str, username: str, password: str) -> None: ...


class KeyringKeyProvider:
    name = "keyring"

    def __init__(self, backend: KeyringBackend) -> None:
        self._backend = backend

    def get_or_create_key(self) -> bytes:
        try:
            stored = self._backend.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if stored:
                return stored.encode()
            key = Fernet.generate_key()
            self._backend.set_password(KEYRING_SERVICE, KEYRING_USERNAME, key.decode())
        except Exception as exc:
            raise ConfigKeyUnavailableError(detail=f"keyring: {type(exc).__name__}") from exc
        return key


class FileKeyProvider:
    name = "key file"

    def __init__(self, config_dir: Path) -> None:
        self._path = config_dir / KEY_FILE_NAME

    @property
    def path(self) -> Path:
        return self._path

    def get_or_create_key(self) -> bytes:
        try:
            if self._path.is_file():
                return self._path.read_bytes().strip()
            self._path.parent.mkdir(parents=True, exist_ok=True)
            key = Fernet.generate_key()
            fd = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, KEY_FILE_POSIX_MODE)
            with os.fdopen(fd, "wb") as handle:
                handle.write(key)
        except OSError as exc:
            raise ConfigKeyUnavailableError(detail=f"key file: {type(exc).__name__}") from exc
        return key


def select_key_provider(
    mode: KeyStorage, config_dir: Path, keyring_backend: KeyringBackend
) -> StoreKeyProvider:
    if mode is KeyStorage.FILE:
        return FileKeyProvider(config_dir)
    if keyring_backend.is_usable():
        return KeyringKeyProvider(keyring_backend)
    if mode is KeyStorage.KEYRING:
        raise ConfigKeyUnavailableError(detail="keyring: no usable backend on this system")
    log.info("no usable OS keyring: using a key file in %s", config_dir)
    return FileKeyProvider(config_dir)
