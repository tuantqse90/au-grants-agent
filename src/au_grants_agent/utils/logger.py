"""Rich-powered logging configuration."""

from __future__ import annotations

import logging

from rich.logging import RichHandler
from rich.theme import Theme

from au_grants_agent.config import settings

NULLSHIFT_THEME = Theme(
    {
        "info": "bold #00ff88",
        "warning": "bold yellow",
        "error": "bold red",
        "repr.number": "#00ff88",
    }
)


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Configure and return the application logger with Rich handler."""
    level = logging.DEBUG if verbose else getattr(logging, settings.log_level, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[
            RichHandler(
                rich_tracebacks=True,
                markup=True,
                show_path=verbose,
            )
        ],
        force=True,
    )
    logger = logging.getLogger("au_grants_agent")
    logger.setLevel(level)
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("au_grants_agent")
