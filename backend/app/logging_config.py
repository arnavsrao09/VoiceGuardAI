"""
Centralized logging configuration for VoiceGuardAI backend.

Sets up structured logging with sensible defaults:
- INFO level for production (startup events, connections, errors)
- DEBUG level available via DEBUG=true in .env
- Suppresses noisy per-frame/per-packet logs unless DEBUG is on
"""

import logging
import sys

from app.config import settings


def setup_logging() -> None:
    """Configure root and app loggers once at startup."""
    level = logging.DEBUG if settings.debug else logging.INFO

    fmt = "[%(levelname).1s] %(name)s: %(message)s"
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger("voiceguard")
    root.setLevel(level)
    if not root.handlers:
        root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("websockets", "asyncio", "urllib3", "httpcore", "httpx", "apscheduler"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    # uvicorn access logs are already visible; don't duplicate
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Return a child logger under the voiceguard namespace."""
    return logging.getLogger(f"voiceguard.{name}")
