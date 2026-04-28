"""structlog setup.

Two output modes:
- Human (default) — key=value lines on stderr (colours disabled in v0.2.1
  for consistent output across terminals; TTY-aware colour comes in ).
- JSON (`--json` CLI flag) — one JSON object per line, suitable for SIEM.
"""
from __future__ import annotations

import logging
import sys
from typing import Any

import structlog


def configure_logging(*, json_output: bool, level: str = "INFO") -> None:
    """Install a structlog configuration appropriate for either CLI mode."""
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=False))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
