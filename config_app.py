"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Claude API
    anthropic_api_key: str = ""

    # OpenClaw webhook auth
    webhook_secret: str = ""

    # Slack / Discord (optional until OpenClaw integration)
    slack_bot_token: str = ""
    slack_app_token: str = ""
    discord_bot_token: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///./claudius.db"

    # LLM provider: "anthropic" (default) or "ollama" (local, free)
    llm_provider: str = "anthropic"
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:14b"

    # Simulation
    simulation_model: str = "claude-sonnet-4-5-20250929"

    # Online product search
    search_backend: str = "mock"  # mock | amazon

    # Environment
    environment: str = "development"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
