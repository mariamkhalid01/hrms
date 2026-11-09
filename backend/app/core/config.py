"""Environment configuration and local upload limits; no automatic data loading."""

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HR_",
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    dataset_storage_dir: Path = Path(__file__).resolve().parents[2] / "runtime" / "datasets"
    max_upload_bytes: int = Field(default=52_428_800, ge=1, le=52_428_800)
    max_rows: int = Field(default=250_000, ge=1, le=250_000)
    max_columns: int = Field(default=200, ge=1, le=200)
    preview_rows: int = Field(default=20, ge=1, le=20)
    inductive_max_events: int = Field(default=50_000, ge=1, le=250_000)
    inductive_max_activities: int = Field(default=100, ge=1, le=500)

    @field_validator("dataset_storage_dir")
    @classmethod
    def resolve_storage(cls, value: Path) -> Path:
        # Relative overrides are anchored to backend/, never the current working directory.
        return (
            value.resolve()
            if value.is_absolute()
            else (Path(__file__).resolve().parents[2] / value).resolve()
        )

    @field_validator("cors_origins")
    @classmethod
    def validate_origins(cls, origins: list[str]) -> list[str]:
        from urllib.parse import urlsplit

        normalized = []
        for origin in origins:
            parsed = urlsplit(origin)
            if (
                parsed.scheme not in {"http", "https"}
                or not parsed.netloc
                or parsed.path not in {"", "/"}
                or parsed.query
                or parsed.fragment
                or parsed.username
                or parsed.password
            ):
                raise ValueError("CORS origins must be explicit HTTP(S) origins without paths")
            normalized.append(origin.rstrip("/"))
        return list(dict.fromkeys(normalized))
