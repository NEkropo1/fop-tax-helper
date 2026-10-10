"""A Monobank account (card, ФОП account, ...) as returned by client-info."""

from pydantic import BaseModel, ConfigDict, Field


class Account(BaseModel):
    """`id` never leaves the backend: the UI works with handles and masked PANs."""

    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    id: str
    currency_code: int = Field(alias="currencyCode")
    type: str | None = None
    iban: str | None = None
    balance: int | None = None
    masked_pan: tuple[str, ...] = Field(default=(), alias="maskedPan")


class ClientInfo(BaseModel):
    model_config = ConfigDict(frozen=True, populate_by_name=True, extra="ignore")

    client_id: str | None = Field(default=None, alias="clientId")
    accounts: tuple[Account, ...] = ()
