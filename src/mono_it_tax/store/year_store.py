"""Encrypted, atomic, versioned store: one Fernet-encrypted JSON document per tax year.

Writes go temp file -> fsync -> backup of the previous version -> os.replace, so a crash leaves
either the old or the new document, never a torn one. Data is never deleted automatically.
"""

import json
import os
import shutil
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from pydantic import ValidationError

from mono_it_tax.config.constants.store import (
    STORE_BACKUP_SUFFIX,
    STORE_FILE_SUFFIX,
    STORE_SCHEMA_VERSION,
    STORE_TEMP_SUFFIX,
)
from mono_it_tax.errors import StoreUnreadableError, StoreWriteError
from mono_it_tax.store.document import YearDocument
from mono_it_tax.store.keys import StoreKeyProvider
from mono_it_tax.store.migrations import MIGRATIONS


class YearStore:
    def __init__(self, directory: Path, key_provider: StoreKeyProvider) -> None:
        self._dir = directory
        self._keys = key_provider
        # The API serves requests on several threads and a fetch job writes in the background. One
        # lock keeps a read from meeting a replace (Windows refuses it) and edits from overwriting
        # each other. Re-entrant: edit() calls load() and save().
        self._lock = threading.RLock()

    @property
    def directory(self) -> Path:
        return self._dir

    def path(self, year: int) -> Path:
        return self._dir / f"{year}{STORE_FILE_SUFFIX}"

    def years(self) -> list[int]:
        if not self._dir.is_dir():
            return []
        return sorted(
            int(p.stem) for p in self._dir.glob(f"*{STORE_FILE_SUFFIX}") if p.stem.isdigit()
        )

    def load(self, year: int) -> YearDocument:
        path = self.path(year)
        with self._lock:
            if not path.is_file():
                return YearDocument(year=year)
            try:
                token = path.read_bytes()
                payload = json.loads(Fernet(self._keys.get_or_create_key()).decrypt(token))
                payload = self._migrate(payload)
                return YearDocument.model_validate(payload)
            except (InvalidToken, ValueError, ValidationError, OSError) as exc:
                raise StoreUnreadableError(path=path) from exc

    def save(self, doc: YearDocument) -> None:
        path = self.path(doc.year)
        with self._lock:
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                token = Fernet(self._keys.get_or_create_key()).encrypt(
                    doc.model_dump_json().encode()
                )
                temp = path.with_suffix(path.suffix + STORE_TEMP_SUFFIX)
                with temp.open("wb") as handle:
                    handle.write(token)
                    handle.flush()
                    os.fsync(handle.fileno())
                if path.is_file():
                    shutil.copyfile(path, path.with_suffix(path.suffix + STORE_BACKUP_SUFFIX))
                temp.replace(path)
            except OSError as exc:
                raise StoreWriteError(path=path) from exc

    @contextmanager
    def edit(self, year: int) -> Iterator[YearDocument]:
        """Read-modify-write as one step: no other thread loads or saves in between. The document
        is saved when the block ends normally; an exception inside saves nothing. Never do network
        calls or sleeps inside the block (it blocks every other store access)."""
        with self._lock:
            doc = self.load(year)
            yield doc
            self.save(doc)

    def delete_year(self, year: int) -> None:
        for suffix in ("", STORE_BACKUP_SUFFIX):
            self.path(year).with_suffix(self.path(year).suffix + suffix).unlink(missing_ok=True)

    def delete_all(self) -> None:
        for year in self.years():
            self.delete_year(year)

    @staticmethod
    def _migrate(payload: dict[str, Any]) -> dict[str, Any]:
        version = int(payload.get("schema_version", 0))
        if version > STORE_SCHEMA_VERSION:
            raise ValueError("document is newer than this app")
        while version < STORE_SCHEMA_VERSION:
            payload = MIGRATIONS[version](payload)
            version += 1
        return payload
