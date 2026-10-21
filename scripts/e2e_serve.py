"""Serve the built Mini App against a temporary PostgreSQL for Playwright."""

import os
import subprocess
import sys
from pathlib import Path

import uvicorn
from testcontainers.community.postgres import PostgresContainer

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    dist = ROOT / "frontend" / "dist" / "index.html"
    if not dist.is_file():
        raise SystemExit("frontend/dist is missing; run pnpm build first")
    with PostgresContainer("postgres:16") as postgres:
        url = _asyncpg_url(postgres.get_connection_url())
        _alembic(url)
        os.environ.update(
            {
                "BOT_TOKEN": "123456:TESTTOKEN",
                "ADMIN_IDS": "1",
                "DATABASE_URL": url,
                "DEEPSEEK_API_KEY": "test-deepseek-key",
                "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
                "DEEPSEEK_MODEL_FAST": "deepseek-flash",
                "DEEPSEEK_MODEL_PRO": "deepseek-v4-pro",
                "DEEPSEEK_TIMEOUT_SEC": "1",
                "DEEPSEEK_MAX_RETRIES": "0",
                "PREMIUM_PRICE_STARS": "250",
                "PAYMENT_HMAC_SECRET": "p" * 32,
                "AUTH_SESSION_SECRET": "a" * 32,
                "APP_ENV": "test",
                "SINGLETON_LOCK": "false",
                "DEV_AUTH_ENABLED": "false",
                "WEBHOOK_URL": "",
                "WEBHOOK_SECRET": "",
                "MINI_APP_URL": "http://127.0.0.1:4173",
                "HOST": "127.0.0.1",
                "PORT": "4173",
                "LOG_LEVEL": "WARNING",
            }
        )
        uvicorn.run(
            "starflow.asgi:create_app",
            factory=True,
            host="127.0.0.1",
            port=4173,
            workers=1,
            log_level="warning",
        )


def _asyncpg_url(url: str) -> str:
    if url.startswith("postgresql+psycopg2://"):
        return url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _alembic(url: str) -> None:
    env = os.environ.copy()
    env.update(
        {
            "BOT_TOKEN": "123456:TESTTOKEN",
            "ADMIN_IDS": "1",
            "DATABASE_URL": url,
            "DEEPSEEK_API_KEY": "test-deepseek-key",
            "DEEPSEEK_BASE_URL": "https://api.deepseek.com",
            "DEEPSEEK_MODEL_FAST": "deepseek-flash",
            "DEEPSEEK_MODEL_PRO": "deepseek-v4-pro",
            "DEEPSEEK_TIMEOUT_SEC": "1",
            "DEEPSEEK_MAX_RETRIES": "0",
            "PREMIUM_PRICE_STARS": "250",
            "PAYMENT_HMAC_SECRET": "p" * 32,
            "AUTH_SESSION_SECRET": "a" * 32,
            "APP_ENV": "test",
            "SINGLETON_LOCK": "false",
            "WEBHOOK_URL": "",
            "WEBHOOK_SECRET": "",
        }
    )
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=ROOT,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr or completed.stdout)


if __name__ == "__main__":
    main()
