#!/usr/bin/env python3
"""
QuantAgent MCP Server — MetaTrader 5 Trading

Exposes MT5 trading tools via MCP (stdio transport).
Communicates with the mt5-bridge REST API server.

Usage:
    python mcp_servers/mt5_trading_server.py

Environment:
    MT5_BRIDGE_URL  — mt5-bridge server URL (default: http://localhost:8000)
"""

import os
import sys

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ── load .env from project root ──────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── local imports ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from utils import error_response, setup_logging, success_response  # noqa: E402

logger = setup_logging("mcp.mt5")

# ── mt5-bridge base URL ─────────────────────────────────────────────────
BASE_URL = os.environ.get("MT5_BRIDGE_URL", "http://localhost:8000").rstrip("/")
TIMEOUT = 15.0

# ── MCP Server ───────────────────────────────────────────────────────────
mcp = FastMCP(
    "MT5 Trading",
    instructions=(
        "MCP server for MetaTrader 5 trading operations via mt5-bridge. "
        "Supports account info, positions, placing orders, modifying TP/SL, "
        "closing positions, and emergency close-all."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
#  Helper
# ═══════════════════════════════════════════════════════════════════════════
def _get(path: str, params: dict | None = None) -> dict | list:
    """GET request to mt5-bridge."""
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict:
    """POST request to mt5-bridge."""
    resp = requests.post(f"{BASE_URL}{path}", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
def mt5_get_account_info() -> str:
    """
    Get MT5 account information including balance, equity, margin,
    free margin, margin level, and leverage.
    """
    try:
        data = _get("/account")
        logger.info("Account info fetched")
        return success_response(data)
    except Exception as e:
        logger.error(f"get_account_info error: {e}")
        return error_response(str(e))


@mcp.tool()
def mt5_get_positions(symbols: str = "") -> str:
    """
    Get all open positions from MT5.

    Args:
        symbols: Comma-separated symbol filter (e.g. "XAUUSD,EURUSD").
                 Leave empty to get ALL open positions.
    """
    try:
        params = {}
        if symbols:
            params["symbols"] = symbols
        data = _get("/positions", params=params)
        count = len(data) if isinstance(data, list) else "unknown"
        logger.info(f"Positions fetched: {count}")
        return success_response(data, f"{count} position(s) found")
    except Exception as e:
        logger.error(f"get_positions error: {e}")
        return error_response(str(e))


@mcp.tool()
def mt5_place_order(
    symbol: str,
    side: str,
    volume: float,
    sl: float = 0.0,
    tp: float = 0.0,
) -> str:
    """
    Place a new market order on MT5.

    Args:
        symbol: Trading symbol (e.g. "XAUUSD", "EURUSD").
        side:   Order direction — "BUY" or "SELL".
        volume: Lot size (e.g. 0.01, 0.1, 1.0).
        sl:     Stop Loss price. 0 = no stop loss.
        tp:     Take Profit price. 0 = no take profit.
    """
    try:
        side = side.upper()
        if side not in ("BUY", "SELL"):
            return error_response(f"Invalid side '{side}'. Must be BUY or SELL.")

        payload: dict = {
            "symbol": symbol.upper(),
            "side": side,
            "volume": volume,
        }
        if sl > 0:
            payload["sl"] = sl
        if tp > 0:
            payload["tp"] = tp

        logger.info(f"Placing order: {payload}")
        data = _post("/order", payload)
        return success_response(data, f"{side} {volume} lot {symbol} — order sent")
    except Exception as e:
        logger.error(f"place_order error: {e}")
        return error_response(str(e))


@mcp.tool()
def mt5_modify_position(
    ticket: int,
    sl: float = 0.0,
    tp: float = 0.0,
) -> str:
    """
    Modify the Stop Loss and/or Take Profit of an existing position.

    Args:
        ticket: Position ticket ID (integer).
        sl:     New Stop Loss price. 0 = remove SL.
        tp:     New Take Profit price. 0 = remove TP.
    """
    try:
        payload: dict = {"ticket": ticket}
        if sl > 0:
            payload["sl"] = sl
        if tp > 0:
            payload["tp"] = tp

        logger.info(f"Modifying position #{ticket}: SL={sl}, TP={tp}")
        data = _post("/modify", payload)
        return success_response(data, f"Position #{ticket} modified")
    except Exception as e:
        logger.error(f"modify_position error: {e}")
        return error_response(str(e))


@mcp.tool()
def mt5_close_position(ticket: int) -> str:
    """
    Close a specific position by its ticket ID.

    Args:
        ticket: Position ticket ID to close.
    """
    try:
        logger.info(f"Closing position #{ticket}")
        data = _post("/close", {"ticket": ticket})
        return success_response(data, f"Position #{ticket} closed")
    except Exception as e:
        logger.error(f"close_position error: {e}")
        return error_response(str(e))


@mcp.tool()
def mt5_close_all(symbol: str = "") -> str:
    """
    Close ALL open positions. Optionally filter by symbol.
    Use with caution — this is a panic/emergency close.

    Args:
        symbol: If provided, only close positions for this symbol.
                Leave empty to close ALL positions.
    """
    try:
        params = {}
        if symbol:
            params["symbols"] = symbol.upper()

        positions = _get("/positions", params=params)
        if not positions:
            return success_response([], "No open positions to close")

        results = []
        for pos in positions:
            tid = pos.get("ticket")
            try:
                res = _post("/close", {"ticket": tid})
                results.append({"ticket": tid, "result": "closed", "detail": res})
                logger.info(f"Closed #{tid}")
            except Exception as ex:
                results.append({"ticket": tid, "result": "error", "detail": str(ex)})
                logger.error(f"Failed to close #{tid}: {ex}")

        return success_response(results, f"Attempted to close {len(results)} position(s)")
    except Exception as e:
        logger.error(f"close_all error: {e}")
        return error_response(str(e))


@mcp.tool()
def mt5_check_health() -> str:
    """Check if the mt5-bridge server and MT5 terminal are connected."""
    try:
        data = _get("/health")
        return success_response(data)
    except Exception as e:
        return error_response(f"mt5-bridge unreachable: {e}")


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info(f"Starting MT5 MCP Server (bridge: {BASE_URL})")
    mcp.run(transport="stdio")
