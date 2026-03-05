"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Central configuration sourced from .env / environment."""

    def __init__(self) -> None:
        # LLM provider: "deepseek" or "anthropic"
        self.llm_provider: str = os.getenv("LLM_PROVIDER", "deepseek").lower()

        # DeepSeek config
        self.deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        self.deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

        # Anthropic config
        self.anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
        self.anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

        # General
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
        if self.llm_provider == "deepseek":
            return self.deepseek_model
        return self.anthropic_model

    @property
    def has_api_key(self) -> bool:
        if self.llm_provider == "deepseek":
            return bool(self.deepseek_api_key) and self.deepseek_api_key != "sk-..."
        return bool(self.anthropic_api_key) and self.anthropic_api_key != "sk-ant-..."

    @property
    def provider_display(self) -> str:
        if self.llm_provider == "deepseek":
            return f"DeepSeek ({self.deepseek_model})"
        return f"Anthropic ({self.anthropic_model})"

    def ensure_dirs(self) -> None:
        """Create required directories if they don't exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.proposals_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
