#!/usr/bin/env python3
"""
QuantAgent MCP Server — Bitkub Trading (Spot)

Exposes Bitkub Spot trading tools via MCP (stdio transport).
Uses direct HTTP requests with HMAC-SHA256 signing per Bitkub API v3.

Usage:
    python mcp_servers/bitkub_trading_server.py

Environment:
    BITKUB_API_KEY    — Bitkub API key
    BITKUB_API_SECRET — Bitkub API secret
"""

import hashlib
import hmac
import json
import os
import sys
from typing import Any

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ── load .env from project root ──────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── local imports ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from utils import error_response, setup_logging, success_response  # noqa: E402

logger = setup_logging("mcp.bitkub")

# ── Bitkub credentials ──────────────────────────────────────────────────
BASE_URL = "https://api.bitkub.com"
API_KEY = os.environ.get("BITKUB_API_KEY", "")
API_SECRET = os.environ.get("BITKUB_API_SECRET", "")
TIMEOUT = 15.0

if not API_KEY or not API_SECRET:
    logger.warning(
        "BITKUB_API_KEY / BITKUB_API_SECRET not set. "
        "Trading tools will fail. Read-only public tools may still work."
    )

# ── MCP Server ───────────────────────────────────────────────────────────
mcp = FastMCP(
    "Bitkub Trading",
    instructions=(
        "MCP server for Bitkub Spot trading. "
        "Supports checking balances, viewing open orders, placing buy/sell orders, "
        "cancelling orders, getting ticker prices, and emergency sell-all to THB."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
#  Internal — HMAC Signing
# ═══════════════════════════════════════════════════════════════════════════


def _get_server_time() -> str:
    """Get Bitkub server time in milliseconds (string)."""
    resp = requests.get(f"{BASE_URL}/api/v3/servertime", timeout=TIMEOUT)
    resp.raise_for_status()
    return str(resp.json())  # Returns an integer timestamp


def _sign(timestamp: str, method: str, path: str, body: str = "") -> str:
    """
    Create HMAC-SHA256 signature per Bitkub API v3 spec.
    payload = timestamp + method + path + body
    """
    payload = f"{timestamp}{method}{path}{body}"
    return hmac.new(
        API_SECRET.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _signed_headers(method: str, path: str, body: str = "") -> dict:
    """Build request headers with authentication."""
    ts = _get_server_time()
    sig = _sign(ts, method, path, body)
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-BTK-APIKEY": API_KEY,
        "X-BTK-TIMESTAMP": ts,
        "X-BTK-SIGN": sig,
    }


def _signed_post(path: str, body: dict | None = None) -> dict:
    """Authenticated POST request."""
    body_str = json.dumps(body) if body else ""
    headers = _signed_headers("POST", path, body_str)
    resp = requests.post(
        f"{BASE_URL}{path}",
        headers=headers,
        data=body_str,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error") != 0:
        raise RuntimeError(f"Bitkub API error code {data.get('error')}: {data}")
    return data


def _signed_get(path: str, params: dict | None = None) -> dict:
    """Authenticated GET request."""
    query = ""
    if params:
        query = "?" + "&".join(f"{k}={v}" for k, v in params.items())
    full_path = path + query
    headers = _signed_headers("GET", full_path)
    resp = requests.get(
        f"{BASE_URL}{full_path}",
        headers=headers,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    if isinstance(data, dict) and data.get("error") != 0:
        raise RuntimeError(f"Bitkub API error code {data.get('error')}: {data}")
    return data


def _public_get(path: str, params: dict | None = None) -> Any:
    """Public (unsigned) GET request."""
    resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ═══════════════════════════════════════════════════════════════════════════
#  Tools
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
def bitkub_get_balances() -> str:
    """
    Get all wallet balances (available + reserved) for each asset.
    Returns only assets with non-zero balances.
    """
    try:
        data = _signed_post("/api/v3/market/balances")
        result = data.get("result", {})
        # Filter non-zero
        non_zero = {
            coin: info
            for coin, info in result.items()
            if isinstance(info, dict)
            and (float(info.get("available", 0)) > 0 or float(info.get("reserved", 0)) > 0)
        }
        return success_response(non_zero, f"{len(non_zero)} asset(s) with balance")
    except Exception as e:
        logger.error(f"get_balances error: {e}")
        return error_response(str(e))


@mcp.tool()
def bitkub_get_open_orders(sym: str) -> str:
    """
    Get open orders for a specific trading pair.

    Args:
        sym: Trading pair symbol (e.g. "BTC_THB", "ETH_THB").
    """
    try:
        data = _signed_get("/api/v3/market/my-open-orders", {"sym": sym.upper()})
        orders = data.get("result", [])
        return success_response(orders, f"{len(orders)} open order(s) for {sym}")
    except Exception as e:
        logger.error(f"get_open_orders error: {e}")
        return error_response(str(e))


@mcp.tool()
def bitkub_place_buy(
    sym: str,
    amt: float,
    rat: float = 0.0,
    typ: str = "market",
) -> str:
    """
    Place a BUY order (place-bid) on Bitkub.

    Args:
        sym: Trading pair (e.g. "btc_thb").
        amt: Amount in THB to spend (e.g. 1000 = spend 1000 THB).
        rat: Rate (price per coin). Set to 0 for market order.
        typ: Order type — "limit" or "market".
    """
    try:
        typ = typ.lower()
        body: dict[str, Any] = {
            "sym": sym.lower(),
            "amt": amt,
            "rat": rat if typ == "limit" else 0,
            "typ": typ,
        }

        logger.info(f"Placing BUY: {body}")
        data = _signed_post("/api/v3/market/place-bid", body)
        return success_response(
            data.get("result"), f"BUY order placed — {amt} THB on {sym}"
        )
    except Exception as e:
        logger.error(f"place_buy error: {e}")
        return error_response(str(e))


@mcp.tool()
def bitkub_place_sell(
    sym: str,
    amt: float,
    rat: float = 0.0,
    typ: str = "market",
) -> str:
    """
    Place a SELL order (place-ask) on Bitkub.

    Args:
        sym: Trading pair (e.g. "btc_thb").
        amt: Amount of crypto to sell (e.g. 0.001 BTC).
        rat: Rate (price per coin). Set to 0 for market order.
        typ: Order type — "limit" or "market".
    """
    try:
        typ = typ.lower()
        body: dict[str, Any] = {
            "sym": sym.lower(),
            "amt": amt,
            "rat": rat if typ == "limit" else 0,
            "typ": typ,
        }

        logger.info(f"Placing SELL: {body}")
        data = _signed_post("/api/v3/market/place-ask", body)
        return success_response(
            data.get("result"), f"SELL order placed — {amt} on {sym}"
        )
    except Exception as e:
        logger.error(f"place_sell error: {e}")
        return error_response(str(e))


@mcp.tool()
def bitkub_cancel_order(sym: str, order_id: str, sd: str) -> str:
    """
    Cancel an open order.

    Args:
        sym:      Trading pair (e.g. "btc_thb").
        order_id: The order ID to cancel.
        sd:       Order side — "buy" or "sell".
    """
    try:
        body = {
            "sym": sym.lower(),
            "id": order_id,
            "sd": sd.lower(),
        }

        logger.info(f"Cancelling order: {body}")
        data = _signed_post("/api/v3/market/cancel-order", body)
        return success_response(data, f"Order #{order_id} cancelled")
    except Exception as e:
        logger.error(f"cancel_order error: {e}")
        return error_response(str(e))


@mcp.tool()
def bitkub_get_ticker(sym: str = "") -> str:
    """
    Get current ticker (price) information.

    Args:
        sym: Trading pair (e.g. "btc_thb"). Leave empty for all tickers.
    """
    try:
        params = {}
        if sym:
            params["sym"] = sym.lower()
        data = _public_get("/api/v3/market/ticker", params)
        if isinstance(data, dict) and "error" in data:
            result = data.get("result", data)
        else:
            result = data
        return success_response(result)
    except Exception as e:
        logger.error(f"get_ticker error: {e}")
        return error_response(str(e))


@mcp.tool()
def bitkub_sell_all() -> str:
    """
    Emergency: sell ALL crypto assets back to THB at market price.
    This iterates through all non-THB balances and places market sell orders.
    Use with extreme caution.
    """
    try:
        # 1. Get balances
        bal_data = _signed_post("/api/v3/market/balances")
        balances = bal_data.get("result", {})

        results = []
        for coin, info in balances.items():
            if coin.upper() == "THB":
                continue
            if not isinstance(info, dict):
                continue
            available = float(info.get("available", 0))
            if available <= 0:
                continue

            sym = f"{coin.lower()}_thb"
            try:
                body = {"sym": sym, "amt": available, "rat": 0, "typ": "market"}
                data = _signed_post("/api/v3/market/place-ask", body)
                results.append(
                    {"coin": coin, "amount": available, "result": "sold", "detail": data.get("result")}
                )
                logger.info(f"Sold {available} {coin}")
            except Exception as ex:
                results.append(
                    {"coin": coin, "amount": available, "result": "error", "detail": str(ex)}
                )
                logger.error(f"Failed to sell {coin}: {ex}")

        if not results:
            return success_response([], "No crypto assets to sell")

        return success_response(results, f"Processed {len(results)} asset(s)")
    except Exception as e:
        logger.error(f"sell_all error: {e}")
        return error_response(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("Starting Bitkub MCP Server")
    mcp.run(transport="stdio")
