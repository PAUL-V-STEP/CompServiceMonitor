"""
Конфигурация и подробное логирование приложения.
"""
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
LOGGER_NAME = "compservice"

# override=True: иначе после смены ключа процесс держит старое значение
load_dotenv(PROJECT_ROOT / ".env", override=True)


class Settings(BaseSettings):
    """Настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    proxy_api_key: str = ""
    proxy_api_base_url: str = "https://api.proxyapi.ru/openai/v1"
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str = "gpt-4o-mini"

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    history_file: str = "history.json"
    max_history_items: int = 10
    sites_config_file: str = ".config"

    parser_timeout: int = 20
    parser_user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    log_level: str = "DEBUG"
    log_file: str = str(LOGS_DIR / "compservice.log")
    log_max_bytes: int = 5 * 1024 * 1024
    log_backup_count: int = 5

    @field_validator("proxy_api_key", mode="before")
    @classmethod
    def strip_key(cls, value):
        return (value or "").strip().strip('"').strip("'")

    @property
    def api_key_ready(self) -> bool:
        key = self.proxy_api_key
        if not key:
            return False
        lowered = key.lower()
        return "your_proxy" not in lowered and not lowered.endswith("here")


settings = Settings()


def _level(name: str) -> int:
    return getattr(logging, str(name).upper(), logging.DEBUG)


def setup_logging() -> logging.Logger:
    """Консоль (INFO+) и ротация файла (DEBUG+) с traceback."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger(LOGGER_NAME)
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.propagate = False

    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-32s | %(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(max(_level(settings.log_level), logging.INFO))
    console.setFormatter(fmt)
    root.addHandler(console)

    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(_level(settings.log_level))
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    for noisy in ("httpx", "httpcore", "openai", "urllib3", "selenium", "WDM", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    root.debug("Логирование инициализировано: file=%s level=%s", settings.log_file, settings.log_level)
    return root


logger = setup_logging()
