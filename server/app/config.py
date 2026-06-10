from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, PostgresDsn, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────
    APP_NAME: str = "super-market"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    ENV: Literal["dev", "staging", "prod"] = "dev"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # ── Server ───────────────────────────────────────────
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: list[str] = ["*"]

    # ── PostgreSQL ───────────────────────────────────────
    DB_DSN: PostgresDsn = PostgresDsn(
        "postgresql+asyncpg://postgres:sjmm@localhost:5432/super_market"
    )
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 10
    DB_ECHO: bool = False

    # ── Redis ────────────────────────────────────────────
    REDIS_DSN: RedisDsn = RedisDsn("redis://localhost:6379/0")
    REDIS_POOL_SIZE: int = 20

    # ── JWT ──────────────────────────────────────────────
    JWT_SECRET: str = "super-market-jwt-secret-key-change-in-production-2024"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Snowflake ────────────────────────────────────────
    SNOWFLAKE_WORKER_ID: int = 1
    SNOWFLAKE_DATACENTER_ID: int = 1

    # ── Arq (queue) ──────────────────────────────────────
    ARQ_REDIS_DSN: RedisDsn = RedisDsn("redis://localhost:6379/1")
    ARQ_POLL_INTERVAL: float = 0.5

    # ── Logging ──────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str = "logs/super-market.log"


    # ── Blockchain ──────────────────────────────────────────
    ETHERSCAN_API_KEY: str = ""
    BSCSCAN_API_KEY: str = ""
    BLOCKCHAIN_POLL_INTERVAL: int = 45


settings = Settings()
