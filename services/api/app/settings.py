# SPDX-FileCopyrightText: 2026 Amin Zoroufi <aminn.zoroufi@gmail.com>
# SPDX-License-Identifier: LicenseRef-Portfolio-Source-Available
"""Environment-only application configuration."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="IIOT_", case_sensitive=False, extra="ignore"
    )

    environment: str = "development"
    database_url: str = "sqlite+pysqlite:///./iiot-local.db"
    jwt_secret: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    ingest_token: SecretStr
    demo_admin_username: str = "demo-admin"
    demo_admin_password: SecretStr
    mqtt_host: str = "localhost"
    mqtt_port: int = Field(default=1883, ge=1, le=65535)
    mqtt_username: str | None = None
    mqtt_password: SecretStr | None = None
    cors_origins: str = "http://localhost:3000"
    offline_after_s: int = Field(default=60, ge=10, le=3600)
    max_query_days: int = Field(default=31, ge=1, le=366)

    @field_validator("jwt_secret", "ingest_token")
    @classmethod
    def validate_secret_length(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("secret must contain at least 32 characters")
        return value

    @field_validator("demo_admin_password")
    @classmethod
    def validate_demo_password(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 12:
            raise ValueError("demo password must contain at least 12 characters")
        return value

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
