from pathlib import Path
from typing import Annotated, Literal, Self
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BeforeValidator, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

from starflow.domain.plans import Plans, load_plans


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _admin_ids(value: object) -> tuple[int, ...]:
    if isinstance(value, tuple):
        return tuple(int(item) for item in value)
    if isinstance(value, str):
        parts = [part.strip() for part in value.split(",") if part.strip()]
        return tuple(int(part) for part in parts)
    raise TypeError("ADMIN_IDS must be a comma-separated list")


def _origins(value: object) -> tuple[str, ...]:
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, str):
        return tuple(part.strip() for part in value.split(",") if part.strip())
    raise TypeError("ALLOWED_ORIGINS must be a comma-separated list")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    bot_token: str
    admin_ids: Annotated[tuple[int, ...], NoDecode, BeforeValidator(_admin_ids)]
    database_url: str
    deepseek_api_key: str
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model_fast: str
    deepseek_model_pro: str
    deepseek_timeout_sec: int = 60
    deepseek_max_retries: int = 3
    premium_price_stars: int = 250
    default_timezone: str = "Europe/Moscow"
    default_locale: str = "ru"
    memory_cache_size: int = 5000
    log_level: str = "INFO"
    webhook_url: str = ""
    webhook_secret: str = ""
    mini_app_url: str = ""
    public_base_url: str = ""
    payment_hmac_secret: str
    auth_session_secret: str
    allowed_origins: Annotated[tuple[str, ...], NoDecode, BeforeValidator(_origins)] = ()
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8000
    web_concurrency: int = 1
    singleton_lock: bool = True
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str = "StarFlow/0.1"
    outbox_interval_sec: int = 30
    auth_max_age_sec: int = 86400
    auth_future_skew_sec: int = 60
    session_ttl_sec: int = 3600
    session_cookie_name: str = "starflow_session"
    dev_auth_enabled: bool = False
    bot_retry_sec: float = 5
    resources_dir: Path = Field(default_factory=lambda: repository_root() / "resources")
    frontend_dist: Path = Field(default_factory=lambda: repository_root() / "frontend" / "dist")
    logo_path: Path = Field(default_factory=lambda: repository_root() / "static" / "logo.png")

    @field_validator("log_level")
    @classmethod
    def _log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in {"DEBUG", "INFO", "WARNING", "ERROR"}:
            raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        return normalized

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.web_concurrency != 1:
            raise ValueError("WEB_CONCURRENCY must be 1")
        if self.port < 1 or self.port > 65535:
            raise ValueError("PORT is out of range")
        if not self.host.strip():
            raise ValueError("HOST is required")
        if not self.database_url.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL must use the postgresql+asyncpg driver")
        if len(self.bot_token.strip()) < 8:
            raise ValueError("BOT_TOKEN is too short")
        if len(self.deepseek_api_key.strip()) < 8:
            raise ValueError("DEEPSEEK_API_KEY is too short")
        if not self.deepseek_model_fast.strip() or not self.deepseek_model_pro.strip():
            raise ValueError("DeepSeek model names are required")
        if self.deepseek_timeout_sec < 1 or self.deepseek_max_retries < 0:
            raise ValueError("DeepSeek timeout and retries are invalid")
        if self.premium_price_stars < 1 or self.memory_cache_size < 1:
            raise ValueError("price and cache size must be positive")
        if self.outbox_interval_sec < 1 or self.auth_max_age_sec < 1 or self.bot_retry_sec <= 0:
            raise ValueError("intervals must be positive")
        if self.session_ttl_sec < 60 or self.auth_future_skew_sec < 0:
            raise ValueError("session lifetime and clock skew are invalid")
        if self.app_env == "production" and self.dev_auth_enabled:
            raise ValueError("DEV_AUTH_ENABLED cannot be true when APP_ENV=production")
        if len(self.payment_hmac_secret) < 32 or len(self.auth_session_secret) < 32:
            raise ValueError("payment and session secrets must be at least 32 characters")
        try:
            ZoneInfo(self.default_timezone)
        except ZoneInfoNotFoundError as error:
            raise ValueError("DEFAULT_TIMEZONE is not an IANA name") from error
        if self.bot_mode == "webhook":
            parts = urlsplit(self.webhook_url.strip())
            path_ok = bool(parts.path) and parts.path != "/"
            if parts.scheme not in {"http", "https"} or not parts.netloc or not path_ok:
                raise ValueError("WEBHOOK_URL must be an absolute URL with a path")
            if len(self.webhook_secret) < 16:
                raise ValueError("WEBHOOK_SECRET is required when WEBHOOK_URL is set")
            if self.app_env == "production" and parts.scheme != "https":
                raise ValueError("production webhook URL must use https")
        self.runtime_plans()
        return self

    @property
    def bot_mode(self) -> Literal["polling", "webhook"]:
        if self.webhook_url.strip():
            return "webhook"
        return "polling"

    @property
    def webhook_path(self) -> str:
        if self.bot_mode != "webhook":
            return ""
        return urlsplit(self.webhook_url.strip()).path

    @property
    def allows_dev_auth(self) -> bool:
        return self.app_env == "local" and self.dev_auth_enabled

    def runtime_plans(self) -> Plans:
        loaded = load_plans(self.resources_dir / "plans.yaml")
        if loaded.premium.price_stars != self.premium_price_stars:
            raise ValueError("PREMIUM_PRICE_STARS does not match resources/plans.yaml")
        return loaded
