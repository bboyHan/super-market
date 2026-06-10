"""Agent Terminal configuration using Pydantic Settings."""

import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables or .env file."""

    # Application metadata
    APP_NAME: str = "agent-terminal"
    APP_VERSION: str = "1.0.0"

    # Server
    HOST: str = "127.0.0.1"
    PORT: int = 8800

    # Database
    DB_PATH: str = str(BASE_DIR / "data" / "agent.db")

    # Playwright browsers path
    PLAYWRIGHT_BROWSERS_PATH: str = "/root/.cache/ms-playwright"

    # Platform API
    PLATFORM_API_BASE: str = "http://localhost:8000"
    AGENT_TOKEN: str = ""  # 由首次登录时的授权码验证设置，不应硬编码

    # Logging
    LOG_DIR: str = str(BASE_DIR / "logs")

    # Collector defaults
    COLLECTOR_BROWSER_HEADLESS: bool = False

    # mitmproxy
    MITMPROXY_PORT: int = 8081

    # Encryption
    COOKIE_ENCRYPT_KEY: str = secrets.token_hex(32)
    ENCRYPTION_SALT: str = secrets.token_hex(16)

    # Task concurrency
    MAX_CONCURRENT_TASKS: int = 3

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()

# Ensure data and log directories exist
os.makedirs(os.path.dirname(settings.DB_PATH), exist_ok=True)
os.makedirs(settings.LOG_DIR, exist_ok=True)
