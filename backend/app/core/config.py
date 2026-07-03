"""Application configuration, loaded from environment variables.

Uses pydantic-settings so that every knob is documented in one place and can be
overridden via the environment (Docker Compose, .env, CI, etc.).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- General ---
    app_name: str = "Formula SE"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)

    # --- Database ---
    database_url: str = Field(
        default="postgresql+psycopg://formulase:formulase@localhost:5432/formulase"
    )
    # In dev we create tables on startup for zero-setup convenience. In Docker/
    # prod this is false and schema is managed by `alembic upgrade head`.
    auto_create_tables: bool = Field(default=True)

    @field_validator("database_url")
    @classmethod
    def _normalize_driver(cls, v: str) -> str:
        """Force the psycopg (v3) driver.

        We ship psycopg3 only, but a bare ``postgresql://`` URL routes SQLAlchemy
        to psycopg2. Operators (e.g. CloudNativePG) hand out ``postgresql://``
        connection strings, so normalize any driverless scheme to
        ``postgresql+psycopg://`` for zero-config integration.
        """
        for prefix in ("postgresql://", "postgres://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v

    # --- Auth / sessions ---
    session_cookie_name: str = "formulase_session"
    session_ttl_hours: int = 24 * 14  # 2 weeks
    cookie_secure: bool = Field(default=False)  # True behind HTTPS in prod
    cookie_samesite: str = Field(default="lax")

    # --- Registration ---
    # Seeded invite code; can be rotated by an admin via settings API.
    default_invite_code: str = Field(default="FORMULA-SE")

    # --- Bootstrap admin (created on first migrate/startup if absent) ---
    bootstrap_admin_email: str | None = Field(default=None)
    bootstrap_admin_password: str | None = Field(default=None)
    bootstrap_admin_name: str = Field(default="Admin")

    # --- Backblaze B2 (S3-compatible) ---
    b2_endpoint_url: str | None = Field(default=None)
    b2_region: str = Field(default="us-east-005")
    b2_key_id: str | None = Field(default=None)
    b2_application_key: str | None = Field(default=None)
    b2_bucket: str = Field(default="formula-se")
    # When B2 isn't configured we fall back to a local filesystem store so the
    # app is runnable end-to-end in dev without cloud credentials.
    local_storage_dir: str = Field(default="/tmp/formula-se-storage")
    presigned_url_ttl_seconds: int = 3600

    # --- Prepared worlds ---
    prepared_world_ttl_hours: int = 24

    # --- Dedicated server push (feature flag) ---
    # Reserved plumbing: MVP ships download only. A concrete WorldDeliverer can
    # be added later behind this flag (see app/services/deliverers).
    server_push_enabled: bool = Field(default=False)

    # --- Block data seed ---
    block_definitions_seed: str = Field(default="data/block_definitions.json")

    @property
    def b2_configured(self) -> bool:
        return bool(self.b2_endpoint_url and self.b2_key_id and self.b2_application_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
