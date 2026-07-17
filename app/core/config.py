from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações carregadas por variáveis de ambiente ou arquivo .env."""

    database_url: str = "sqlite:///./cloud_control.db"
    jwt_secret_key: str = "change-this-development-secret-before-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    @property
    def jwt_access_token_expires_in(self) -> int:
        return self.jwt_access_token_expire_minutes * 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
