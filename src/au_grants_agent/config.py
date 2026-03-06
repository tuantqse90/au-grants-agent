"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration sourced from .env / environment."""

    VALID_PROVIDERS = {"deepseek", "anthropic", "gemini", "openai"}

    def __init__(self) -> None:
        # LLM provider: "deepseek", "anthropic", "gemini", or "openai"
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek").lower()

        # DeepSeek config
        self.deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # Anthropic config
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        # Gemini config
        self.gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

        # OpenAI config
        self.openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
        self.openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o")

        # SMTP / Notifications
        self.smtp_host: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port: int = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user: str = os.getenv("SMTP_USER", "")
        self.smtp_password: str = os.getenv("SMTP_PASSWORD", "")
        self.notify_to: str = os.getenv("NOTIFY_TO", "")

        # Database
        self.database_url: str = os.getenv("DATABASE_URL", "")
        self.db_path: Path = Path(os.getenv("DB_PATH", "data/grants.db"))
        self.crawl_delay: float = float(os.getenv("CRAWL_DELAY", "2.5"))
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.default_export_format: str = os.getenv("DEFAULT_EXPORT_FORMAT", "all")
        self.proposals_dir: Path = Path(os.getenv("PROPOSALS_DIR", "./proposals"))
        self.user_agent: str = "NullShift-GrantBot/1.0 (+https://nullshift.sh; research-purposes)"
        self.max_retries: int = 3
        self.backoff_base: float = 2.0

    @property
    def default_model(self) -> str:
        return {
            "deepseek": self.deepseek_model,
            "anthropic": self.anthropic_model,
            "gemini": self.gemini_model,
            "openai": self.openai_model,
        }.get(self.llm_provider, self.deepseek_model)

    @property
    def has_api_key(self) -> bool:
        key_map = {
            "deepseek": (self.deepseek_api_key, "sk-..."),
            "anthropic": (self.anthropic_api_key, "sk-ant-..."),
            "gemini": (self.gemini_api_key, ""),
            "openai": (self.openai_api_key, "sk-..."),
        }
        key, placeholder = key_map.get(self.llm_provider, ("", ""))
        return bool(key) and key != placeholder

    def get_api_key(self, provider: str) -> str:
        """Get API key for a specific provider."""
        return {
            "deepseek": self.deepseek_api_key,
            "anthropic": self.anthropic_api_key,
            "gemini": self.gemini_api_key,
            "openai": self.openai_api_key,
        }.get(provider, "")

    def get_model(self, provider: str) -> str:
        """Get model name for a specific provider."""
        return {
            "deepseek": self.deepseek_model,
            "anthropic": self.anthropic_model,
            "gemini": self.gemini_model,
            "openai": self.openai_model,
        }.get(provider, "")

    @property
    def use_postgres(self) -> bool:
        """True when DATABASE_URL is set (e.g. Railway PostgreSQL addon)."""
        return bool(self.database_url)

    @property
    def provider_display(self) -> str:
        return f"{self.llm_provider.title()} ({self.default_model})"

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
