"""Settings factory for tests and the OpenAPI export."""

from starflow.config import Settings


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "bot_token": "123456:TESTTOKEN",
        "admin_ids": (1,),
        "database_url": "postgresql+asyncpg://starflow:starflow@127.0.0.1:5432/starflow",
        "deepseek_api_key": "test-deepseek-key",
        "deepseek_base_url": "https://api.deepseek.com",
        "deepseek_model_fast": "deepseek-flash",
        "deepseek_model_pro": "deepseek-v4-pro",
        "payment_hmac_secret": "p" * 32,
        "auth_session_secret": "a" * 32,
        "app_env": "test",
        "singleton_lock": False,
        "webhook_url": "",
        "webhook_secret": "",
        "mini_app_url": "",
        "allowed_origins": (),
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
