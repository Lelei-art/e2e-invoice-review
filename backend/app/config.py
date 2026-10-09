from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPOSITORY_ROOT / "backend" / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_access_name: str | None = None
    app_access_password: SecretStr | None = None
    app_session_secret: SecretStr | None = None
    frontend_dist_dir: Path | None = None
    sqlite_vfs: Literal["unix-dotfile"] | None = None

    @model_validator(mode="after")
    def validate_access_settings(self) -> "Settings":
        if (self.app_access_password is None) != (self.app_session_secret is None):
            raise ValueError(
                "APP_ACCESS_PASSWORD and APP_SESSION_SECRET must be configured together."
            )
        if self.app_access_password is not None and self.app_access_name is None:
            raise ValueError(
                "APP_ACCESS_NAME must be configured when access protection is enabled."
            )
        return self

    @property
    def access_enabled(self) -> bool:
        return self.app_access_password is not None


@lru_cache
def get_settings() -> Settings:
    return Settings()
