from functools import lru_cache

from pydantic import AliasChoices, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_AUTH_SECRET_KEY = "easy-mes-local-dev-secret"


class Settings(BaseSettings):
    app_name: str = Field(default="Easy MES", validation_alias=AliasChoices("APP_NAME", "EASY_MES_APP_NAME"))
    app_env: str = Field(default="local", validation_alias=AliasChoices("APP_ENV", "EASY_MES_APP_ENV"))
    api_v1_prefix: str = Field(
        default="/api/v1",
        validation_alias=AliasChoices("API_V1_PREFIX", "EASY_MES_API_V1_PREFIX"),
    )
    database_url: str = Field(
        default="postgresql+asyncpg://easy_mes:easy_mes@127.0.0.1:15432/easy_mes",
        validation_alias=AliasChoices("DATABASE_URL", "EASY_MES_DATABASE_URL"),
    )
    auth_secret_key: SecretStr = Field(
        default=DEFAULT_AUTH_SECRET_KEY,
        validation_alias=AliasChoices("AUTH_SECRET_KEY", "EASY_MES_AUTH_SECRET_KEY"),
    )
    access_token_expire_minutes: int = Field(
        default=480,
        validation_alias=AliasChoices("ACCESS_TOKEN_EXPIRE_MINUTES", "EASY_MES_ACCESS_TOKEN_EXPIRE_MINUTES"),
    )
    cors_origins: str = Field(
        default="http://127.0.0.1:5180,http://localhost:5180",
        validation_alias=AliasChoices("CORS_ORIGINS", "EASY_MES_CORS_ORIGINS"),
    )
    log_level: str = Field(default="INFO", validation_alias=AliasChoices("LOG_LEVEL", "EASY_MES_LOG_LEVEL"))

    @model_validator(mode="after")
    def validate_production_secret(self) -> "Settings":
        if self.app_env.lower() != "local" and self.auth_secret_key.get_secret_value() == DEFAULT_AUTH_SECRET_KEY:
            raise RuntimeError("AUTH_SECRET_KEY must be changed when APP_ENV is not local.")
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
