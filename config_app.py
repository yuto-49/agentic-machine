"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Claude API
    anthropic_api_key: str = ""

    # OpenClaw webhook auth
    webhook_secret: str = ""

    # Slack / Discord (optional until OpenClaw integration)
    slack_bot_token: str = ""
    discord_bot_token: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./claudius.db"

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
