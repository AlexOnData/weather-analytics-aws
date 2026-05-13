"""Structured logging — CloudWatch equivalent for the local stack."""

from __future__ import annotations

import sys

from loguru import logger

from src.config import LOGS_DIR


def configure_logging(component: str) -> None:
    """Attach a console + per-component file sink. Idempotent per process.

    Falls back to stderr-only logging if the LOGS_DIR is not writable
    (e.g. Streamlit Community Cloud sandbox)."""
    logger.remove()
    logger.add(
        sys.stderr,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan> - <level>{message}</level>",
    )
    try:
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOGS_DIR / f"{component}.log"
        logger.add(
            log_file,
            level="DEBUG",
            rotation="10 MB",
            retention="14 days",
            format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        )
    except (OSError, PermissionError):
        pass


def get_logger(component: str = "weatherlens"):
    """Return a logger bound to a component name."""
    return logger.bind(component=component)
