import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from mono_it_tax.config.constants.store import STORE_SCHEMA_VERSION
from mono_it_tax.config.enums import Currency, KeyStorage, MarkSource, Period
from mono_it_tax.domain.account import Account
from mono_it_tax.domain.income import Mark
from mono_it_tax.errors import ConfigKeyUnavailableError, StoreUnreadableError
from mono_it_tax.store.document import DeclarationInput, YearDocument
from mono_it_tax.store.keys import (
    FileKeyProvider,
    KeyringKeyProvider,
    StoreKeyProvider,
    select_key_provider,
)
from mono_it_tax.store.migrations import MIGRATIONS
from mono_it_tax.store.year_store import YearStore
from tests.support import make_payment

NOW = datetime(2026, 10, 10, tzinfo=UTC)


class FixedKey:
    name = "fixed"

    def __init__(self, key: bytes | None = None) -> None:
        self.key = key or Fernet.generate_key()

    def get_or_create_key(self) -> bytes:
        return self.key


class FakeKeyring:
    def __init__(self, *, usable: bool = True, broken: bool = False) -> None:
        self.usable = usable
        self.broken = broken
        self.items: dict[tuple[str, str], str] = {}

    def is_usable(self) -> bool:
        return self.usable

    def get_password(self, service: str, username: str) -> str | None:
        if self.broken:
            raise RuntimeError("locked")
        return self.items.get((service, username))

    def set_password(self, service: str, username: str, password: str) -> None:
        self.items[(service, username)] = password


def rich_document() -> YearDocument:
    payment = make_payment("p1", amount=123_456, counterName="ТОВ Ромашка")
    usd = make_payment("p2", currency=Currency.USD)
    doc = YearDocument(year=2026)
    doc.payments = {payment.id: payment, usd.id: usd}
    doc.marks = {"p1": Mark(payment_id="p1", amount_override=Decimal("1000.50"))}
    doc.rates = {Currency.USD: {date(2026, 7, 1): Decimal("41.1234")}}
    doc.declarations = [
        DeclarationInput(
            period=Period.H1,
            income=Decimal("1"),
            row_07_income_15=Decimal(0),
            row_12_tax=Decimal("0.05"),
            row_23_levy=Decimal("0.01"),
            source=MarkSource.MANUAL,
            entered_at=NOW,
        )
    ]
    return doc


def test_roundtrip_keeps_every_type(tmp_path: Path) -> None:
    store = YearStore(tmp_path, FixedKey())
    doc = rich_document()
    store.save(doc)
    loaded = store.load(2026)
    assert loaded == doc
    assert loaded.payments["p1"].raw["id"] == "p1"
    assert loaded.rates[Currency.USD][date(2026, 7, 1)] == Decimal("41.1234")


def test_missing_year_is_an_empty_document(tmp_path: Path) -> None:
    assert YearStore(tmp_path, FixedKey()).load(2030) == YearDocument(year=2030)


def test_file_is_encrypted_at_rest(tmp_path: Path) -> None:
    store = YearStore(tmp_path, FixedKey())
    store.save(rich_document())
    blob = store.path(2026).read_bytes()
    assert blob.startswith(b"gAAAA")  # Fernet token, not JSON
    assert b"counterName" not in blob
    assert "Ромашка".encode() not in blob


def test_wrong_key_and_tampering_are_unreadable_not_a_crash(tmp_path: Path) -> None:
    YearStore(tmp_path, FixedKey()).save(rich_document())
    with pytest.raises(StoreUnreadableError):
        YearStore(tmp_path, FixedKey()).load(2026)  # another key
    store = YearStore(tmp_path, FixedKey())
    path = store.path(2027)
    path.write_bytes(b"not a fernet token")
    with pytest.raises(StoreUnreadableError):
        store.load(2027)


def test_document_from_a_newer_app_is_unreadable(tmp_path: Path) -> None:
    key = FixedKey()
    store = YearStore(tmp_path, key)
    payload = (
        YearDocument(year=2026)
        .model_dump_json()
        .replace(f'"schema_version":{STORE_SCHEMA_VERSION}', '"schema_version":99')
    )
    store.path(2026).write_bytes(Fernet(key.key).encrypt(payload.encode()))
    with pytest.raises(StoreUnreadableError):
        store.load(2026)


def test_migrations_run_in_order(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key = FixedKey()
    store = YearStore(tmp_path, key)
    old = (
        YearDocument(year=2026)
        .model_dump_json()
        .replace(f'"schema_version":{STORE_SCHEMA_VERSION}', '"schema_version":0')
    )
    store.path(2026).write_bytes(Fernet(key.key).encrypt(old.encode()))
    monkeypatch.setitem(MIGRATIONS, 0, lambda payload: {**payload, "schema_version": 1})
    assert store.load(2026).schema_version == STORE_SCHEMA_VERSION


def test_v1_payment_currency_becomes_the_account_currency(tmp_path: Path) -> None:
    """v1 stored the bank's operation currency as the payment currency (a USD->UAH-card transfer
    was counted as USD). The migration restores the account currency and keeps the old value."""
    key = FixedKey()
    store = YearStore(tmp_path, key)
    uah_card = Account(id="acc-1", currency_code=980)
    doc = YearDocument(
        year=2026,
        accounts=(uah_card,),
        payments={
            "conv": make_payment("conv", currency=Currency.UAH),
            "orphan": make_payment("orphan", currency=Currency.UAH, account_id="gone"),
        },
    )
    v1 = json.loads(doc.model_dump_json())
    v1["schema_version"] = 1
    for payment in v1["payments"].values():
        del payment["operation_currency"]
    v1["payments"]["conv"]["currency"] = "USD"  # the bank's currencyCode of the operation
    v1["payments"]["orphan"]["currency"] = "USD"
    store.path(2026).write_bytes(Fernet(key.key).encrypt(json.dumps(v1).encode()))

    loaded = store.load(2026)

    assert loaded.schema_version == STORE_SCHEMA_VERSION
    conv = loaded.payments["conv"]
    assert (conv.currency, conv.operation_currency) == (Currency.UAH, Currency.USD)
    orphan = loaded.payments["orphan"]  # account not cached: nothing to correct it with
    assert (orphan.currency, orphan.operation_currency) == (Currency.USD, Currency.USD)


def test_second_save_keeps_a_backup_of_the_previous_version(tmp_path: Path) -> None:
    store = YearStore(tmp_path, FixedKey())
    first = YearDocument(year=2026)
    store.save(first)
    second = rich_document()
    store.save(second)
    assert store.load(2026) == second
    backup = store.path(2026).with_suffix(".enc.bak")
    assert backup.is_file()


def test_failed_write_leaves_the_old_document_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = YearStore(tmp_path, FixedKey())
    original = rich_document()
    store.save(original)

    def explode(self: Path, target: Path) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(Path, "replace", explode)
    with pytest.raises(OSError, match="disk full"):
        store.save(YearDocument(year=2026))
    monkeypatch.undo()
    assert store.load(2026) == original


def test_years_and_explicit_deletion(tmp_path: Path) -> None:
    store = YearStore(tmp_path, FixedKey())
    assert store.years() == []
    store.save(YearDocument(year=2025))
    store.save(YearDocument(year=2026))
    store.save(YearDocument(year=2026))  # creates a backup too
    assert store.years() == [2025, 2026]
    store.delete_year(2026)
    assert store.years() == [2025]
    assert not list(tmp_path.glob("2026*"))
    store.delete_all()
    assert store.years() == []


def test_file_key_is_created_once_reused_and_lives_outside_data(tmp_path: Path) -> None:
    provider = FileKeyProvider(tmp_path / "config")
    key = provider.get_or_create_key()
    assert provider.get_or_create_key() == key
    assert provider.path.parent == tmp_path / "config"
    Fernet(key)  # a valid Fernet key


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_file_key_is_owner_only(tmp_path: Path) -> None:
    provider = FileKeyProvider(tmp_path)
    provider.get_or_create_key()
    assert provider.path.stat().st_mode & 0o777 == 0o600


def test_file_key_failure_is_a_config_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(ConfigKeyUnavailableError):
        FileKeyProvider(blocker / "sub").get_or_create_key()


def test_keyring_key_is_generated_once_and_reused() -> None:
    backend = FakeKeyring()
    first = KeyringKeyProvider(backend).get_or_create_key()
    assert KeyringKeyProvider(backend).get_or_create_key() == first


def test_keyring_failure_is_a_config_error() -> None:
    with pytest.raises(ConfigKeyUnavailableError):
        KeyringKeyProvider(FakeKeyring(broken=True)).get_or_create_key()


def names(provider: StoreKeyProvider) -> str:
    return provider.name


def test_auto_prefers_keyring_then_falls_back_to_a_key_file(tmp_path: Path) -> None:
    assert names(select_key_provider(KeyStorage.AUTO, tmp_path, FakeKeyring())) == "keyring"
    fallback = select_key_provider(KeyStorage.AUTO, tmp_path, FakeKeyring(usable=False))
    assert names(fallback) == "key file"


def test_forced_modes(tmp_path: Path) -> None:
    assert names(select_key_provider(KeyStorage.FILE, tmp_path, FakeKeyring())) == "key file"
    with pytest.raises(ConfigKeyUnavailableError):
        select_key_provider(KeyStorage.KEYRING, tmp_path, FakeKeyring(usable=False))
