from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas por variáveis de ambiente ou arquivo .env."""

    database_url: str
    jwt_secret_key: str
    jwt_algorithm: str
    jwt_access_token_expire_minutes: int

    # Headscale Integration Settings
    headscale_url: str = ""
    headscale_api_key: str = ""
    headscale_timeout: int = 10

    @field_validator("headscale_url", mode="before")
    @classmethod
    def format_headscale_url(cls, v: str) -> str:
        if not v:
            return ""
        url = v.strip().rstrip("/")
        if url and not (url.startswith("http://") or url.startswith("https://")):
            url = f"http://{url}"
        return url

    @property
    def jwt_access_token_expires_in(self) -> int:
        return self.jwt_access_token_expire_minutes * 60

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
