"""
Shared utilities for QuantAgent MCP Trading Servers.

Provides:
- Structured JSON response formatting for MCP tool results.
- Logging configuration.
"""

import json
import logging
import os
import sys
from typing import Any


def setup_logging(name: str) -> logging.Logger:
    """
    Configure a logger that writes to stderr (so it doesn't pollute stdio MCP transport).
    """
    logger = logging.getLogger(name)
    logger.setLevel(os.environ.get("LOG_LEVEL", "INFO").upper())

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s")
    )
    logger.addHandler(handler)
    return logger


def success_response(data: Any, message: str = "OK") -> str:
    """Format a successful tool response as JSON string."""
    return json.dumps(
        {"status": "success", "message": message, "data": data},
        indent=2,
        default=str,
        ensure_ascii=False,
    )


def error_response(error: str, details: Any = None) -> str:
    """Format an error tool response as JSON string."""
    payload: dict[str, Any] = {"status": "error", "error": error}
    if details is not None:
        payload["details"] = details
    return json.dumps(payload, indent=2, default=str, ensure_ascii=False)
