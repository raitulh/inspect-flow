from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(BASE_DIR.parent / ".env"), str(BASE_DIR / ".env")),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "LineGuard CV"
    app_env: str = "development"
    secret_key: str = "local-development-only-change-before-deployment"
    database_url: str = f"sqlite:///{(BASE_DIR / 'lineguard.db').as_posix()}"
    storage_root: Path = BASE_DIR / "data"
    max_upload_mb: int = Field(default=200, ge=1, le=2048)
    allowed_video_extensions: list[str] = [".mp4", ".mov", ".avi", ".mkv", ".webm"]
    access_token_minutes: int = Field(default=480, ge=5, le=1440)
    cookie_secure: bool = False
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    worker_poll_seconds: float = Field(default=1.0, ge=0.1, le=30)
    max_sampled_frames: int = Field(default=1200, ge=1, le=100000)
    default_frame_stride: int = Field(default=10, ge=1, le=300)
    demo_mode: bool = False
    live_camera_sample_seconds: float = Field(default=1.0, ge=0.2, le=60)
    live_event_dedupe_seconds: int = Field(default=60, ge=1, le=3600)
    storage_retention_days: int = Field(default=30, ge=0, le=3650)
    webhook_url: str | None = None
    webhook_secret: str | None = None

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_origins(cls, value):
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

    @model_validator(mode="after")
    def validate_production_secrets(self):
        if self.app_env.lower() in {"production", "prod"}:
            if self.secret_key == "local-development-only-change-before-deployment" or len(self.secret_key) < 32:
                raise ValueError("Set a strong SECRET_KEY (at least 32 characters) in production")
            if not self.cookie_secure:
                raise ValueError("COOKIE_SECURE must be true in production")
            if "*" in self.cors_origins:
                raise ValueError("Wildcard CORS is not allowed in production")
        return self


@lru_cache

def get_settings() -> Settings:
    return Settings()
