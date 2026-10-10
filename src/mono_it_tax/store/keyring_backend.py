"""Adapter from the real `keyring` package to our KeyringBackend protocol."""

import keyring
import keyring.backends.fail
import keyring.errors


class SystemKeyring:
    def is_usable(self) -> bool:
        backend = keyring.get_keyring()
        return not isinstance(backend, keyring.backends.fail.Keyring) and backend.priority > 0

    def get_password(self, service: str, username: str) -> str | None:
        return keyring.get_password(service, username)

    def set_password(self, service: str, username: str, password: str) -> None:
        keyring.set_password(service, username, password)
