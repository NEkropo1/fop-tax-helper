"""Only values a user may plausibly tune live here (via .env / environment)."""

from pathlib import Path

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from mono_it_tax.config.enums import KeyStorage

# src/mono_it_tax/config/settings.py -> project root. Anchoring here (not to the CWD) makes the app
# work no matter where it is launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", extra="ignore")

    monobank_token: SecretStr = SecretStr("")
    data_dir: Path = Path("data")
    http_timeout_s: float = 30.0
    retry_attempts: int = 3
    retry_backoff_s: float = 2.0
    key_storage: KeyStorage = KeyStorage.AUTO

    @field_validator("data_dir")
    @classmethod
    def _anchor_data_dir(cls, v: Path) -> Path:
        return v if v.is_absolute() else PROJECT_ROOT / v

    @property
    def rules_dir(self) -> Path:
        return self.data_dir / "rules"
