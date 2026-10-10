"""Opaque, stable account handles: real account ids / IBANs never go to the browser."""

import hashlib
import hmac
from collections.abc import Iterable

from mono_it_tax.config.constants.money import HANDLE_LENGTH
from mono_it_tax.domain.account import Account
from mono_it_tax.errors import UnknownAccountError


class AccountHandles:
    """HMAC of the account id under the store key: stable across restarts, useless to guess."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def of(self, account_id: str) -> str:
        digest = hmac.new(self._key, account_id.encode(), hashlib.sha256).hexdigest()
        return digest[:HANDLE_LENGTH]

    def resolve(self, handle: str, accounts: Iterable[Account]) -> str:
        for account in accounts:
            if hmac.compare_digest(self.of(account.id), handle):
                return account.id
        raise UnknownAccountError
