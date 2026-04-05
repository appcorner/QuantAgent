#!/usr/bin/env python3
"""
QuantAgent MCP Server — Binance Trading (Spot & USDS-M Futures)

Exposes Binance trading tools via MCP (stdio transport).
Uses the python-binance library for all API interactions.

Usage:
    python mcp_servers/binance_trading_server.py

Environment:
    BINANCE_API_KEY    — Binance API key
    BINANCE_API_SECRET — Binance API secret
"""

import os
import sys

from binance.client import Client
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# ── load .env from project root ──────────────────────────────────────────
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# ── local imports ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))
from utils import error_response, setup_logging, success_response  # noqa: E402

logger = setup_logging("mcp.binance")

# ── Binance Client ───────────────────────────────────────────────────────
API_KEY = os.environ.get("BINANCE_API_KEY", "")
API_SECRET = os.environ.get("BINANCE_API_SECRET", "")

if not API_KEY or not API_SECRET:
    logger.warning(
        "BINANCE_API_KEY / BINANCE_API_SECRET not set. "
        "Trading tools will fail. Read-only public tools may still work."
    )

client = Client(API_KEY, API_SECRET)

# ── MCP Server ───────────────────────────────────────────────────────────
mcp = FastMCP(
    "Binance Trading",
    instructions=(
        "MCP server for Binance Spot and USDS-M Futures trading. "
        "Supports account balance, positions, placing orders, cancelling orders, "
        "closing positions, leverage management, and emergency close-all."
    ),
)


# ═══════════════════════════════════════════════════════════════════════════
#  Tools — Account & Info
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
def binance_get_account(market_type: str = "spot") -> str:
    """
    Get Binance account balance information.

    Args:
        market_type: "spot" for Spot wallet, "futures" for USDS-M Futures wallet.
    """
    try:
        market_type = market_type.lower()
        if market_type == "futures":
            balances = client.futures_account_balance()
            # Filter to non-zero balances
            non_zero = [
                b
                for b in balances
                if float(b.get("balance", 0)) != 0
                or float(b.get("crossUnPnl", 0)) != 0
            ]
            return success_response(non_zero, f"{len(non_zero)} asset(s) with balance")
        else:
            info = client.get_account()
            balances = [
                b
                for b in info.get("balances", [])
                if float(b.get("free", 0)) > 0 or float(b.get("locked", 0)) > 0
            ]
            return success_response(
                {"balances": balances, "canTrade": info.get("canTrade")},
                f"{len(balances)} asset(s) with balance",
            )
    except BinanceAPIException as e:
        logger.error(f"get_account error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"get_account error: {e}")
        return error_response(str(e))


@mcp.tool()
def binance_get_positions(symbol: str = "") -> str:
    """
    Get open Futures positions (USDS-M).

    Args:
        symbol: Specific symbol (e.g. "BTCUSDT"). Leave empty for all positions.
    """
    try:
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()
        positions = client.futures_position_information(**params)
        # Filter to positions with actual exposure
        active = [
            p for p in positions if float(p.get("positionAmt", 0)) != 0
        ]
        return success_response(active, f"{len(active)} active position(s)")
    except BinanceAPIException as e:
        logger.error(f"get_positions error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"get_positions error: {e}")
        return error_response(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  Tools — Order Management
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
def binance_place_order(
    market_type: str,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: float = 0.0,
    stop_price: float = 0.0,
    time_in_force: str = "GTC",
) -> str:
    """
    Place an order on Binance (Spot or Futures).

    Args:
        market_type:   "spot" or "futures".
        symbol:        Trading pair (e.g. "BTCUSDT").
        side:          "BUY" or "SELL".
        order_type:    "MARKET", "LIMIT", "STOP_MARKET", "TAKE_PROFIT_MARKET".
        quantity:      Order quantity (base asset).
        price:         Limit price (required for LIMIT orders, ignored for MARKET).
        stop_price:    Stop/Trigger price (for STOP_MARKET or TAKE_PROFIT_MARKET).
        time_in_force: Time in force — "GTC", "IOC", "FOK" (for LIMIT orders).
    """
    try:
        side = side.upper()
        order_type = order_type.upper()
        symbol = symbol.upper()
        market_type = market_type.lower()

        if side not in ("BUY", "SELL"):
            return error_response(f"Invalid side '{side}'. Must be BUY or SELL.")

        params: dict = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        # Add price for LIMIT orders
        if order_type == "LIMIT":
            if price <= 0:
                return error_response("Price is required for LIMIT orders.")
            params["price"] = price
            params["timeInForce"] = time_in_force

        # Add stopPrice for stop orders
        if order_type in ("STOP_MARKET", "TAKE_PROFIT_MARKET") and stop_price > 0:
            params["stopPrice"] = stop_price

        logger.info(f"Placing {market_type} order: {params}")

        if market_type == "futures":
            result = client.futures_create_order(**params)
        else:
            result = client.create_order(**params)

        return success_response(result, f"{side} {quantity} {symbol} — order placed")
    except BinanceAPIException as e:
        logger.error(f"place_order error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"place_order error: {e}")
        return error_response(str(e))


@mcp.tool()
def binance_cancel_order(
    market_type: str, symbol: str, order_id: int
) -> str:
    """
    Cancel an open order.

    Args:
        market_type: "spot" or "futures".
        symbol:      Trading pair (e.g. "BTCUSDT").
        order_id:    The order ID to cancel.
    """
    try:
        symbol = symbol.upper()
        market_type = market_type.lower()

        logger.info(f"Cancelling order #{order_id} on {market_type} {symbol}")

        if market_type == "futures":
            result = client.futures_cancel_order(symbol=symbol, orderId=order_id)
        else:
            result = client.cancel_order(symbol=symbol, orderId=order_id)

        return success_response(result, f"Order #{order_id} cancelled")
    except BinanceAPIException as e:
        logger.error(f"cancel_order error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"cancel_order error: {e}")
        return error_response(str(e))


@mcp.tool()
def binance_close_position(symbol: str, side: str, quantity: float) -> str:
    """
    Close (reduce) a Futures position by placing a reduceOnly market order.

    Args:
        symbol:   Trading pair (e.g. "BTCUSDT").
        side:     The CLOSING side — "BUY" to close a SHORT, "SELL" to close a LONG.
        quantity: Amount to close. Use the full positionAmt to close entirely.
    """
    try:
        symbol = symbol.upper()
        side = side.upper()

        params = {
            "symbol": symbol,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
            "reduceOnly": True,
        }

        logger.info(f"Closing futures position: {params}")
        result = client.futures_create_order(**params)
        return success_response(result, f"Position {symbol} reduced by {quantity}")
    except BinanceAPIException as e:
        logger.error(f"close_position error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"close_position error: {e}")
        return error_response(str(e))


@mcp.tool()
def binance_close_all(market_type: str = "futures") -> str:
    """
    Emergency: close ALL positions or sell all Spot assets to USDT.

    For Futures: market-close every active position.
    For Spot: market-sell every non-USDT asset.

    Args:
        market_type: "futures" or "spot".
    """
    try:
        market_type = market_type.lower()
        results = []

        if market_type == "futures":
            positions = client.futures_position_information()
            active = [p for p in positions if float(p.get("positionAmt", 0)) != 0]

            if not active:
                return success_response([], "No active futures positions")

            for pos in active:
                sym = pos["symbol"]
                amt = float(pos["positionAmt"])
                # If amt > 0, we're long → SELL to close; if < 0, short → BUY to close
                close_side = "SELL" if amt > 0 else "BUY"
                close_qty = abs(amt)
                try:
                    res = client.futures_create_order(
                        symbol=sym,
                        side=close_side,
                        type="MARKET",
                        quantity=close_qty,
                        reduceOnly=True,
                    )
                    results.append({"symbol": sym, "result": "closed", "detail": res})
                    logger.info(f"Closed futures {sym} {close_qty}")
                except Exception as ex:
                    results.append({"symbol": sym, "result": "error", "detail": str(ex)})
                    logger.error(f"Failed to close {sym}: {ex}")
        else:
            # Spot: sell all non-USDT assets
            info = client.get_account()
            balances = [
                b
                for b in info.get("balances", [])
                if float(b.get("free", 0)) > 0 and b["asset"] not in ("USDT", "BUSD", "USD")
            ]

            if not balances:
                return success_response([], "No Spot assets to sell")

            for bal in balances:
                asset = bal["asset"]
                free = float(bal["free"])
                sym = f"{asset}USDT"
                try:
                    res = client.create_order(
                        symbol=sym, side="SELL", type="MARKET", quantity=free
                    )
                    results.append({"asset": asset, "result": "sold", "detail": res})
                    logger.info(f"Sold {free} {asset}")
                except Exception as ex:
                    results.append({"asset": asset, "result": "error", "detail": str(ex)})
                    logger.error(f"Failed to sell {asset}: {ex}")

        return success_response(results, f"Processed {len(results)} item(s)")
    except BinanceAPIException as e:
        logger.error(f"close_all error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"close_all error: {e}")
        return error_response(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  Tools — Futures Management
# ═══════════════════════════════════════════════════════════════════════════


@mcp.tool()
def binance_set_leverage(symbol: str, leverage: int) -> str:
    """
    Set leverage for a Futures symbol.

    Args:
        symbol:   Trading pair (e.g. "BTCUSDT").
        leverage: Leverage multiplier (e.g. 1, 5, 10, 20, 50, 125).
    """
    try:
        symbol = symbol.upper()
        logger.info(f"Setting leverage {leverage}x for {symbol}")
        result = client.futures_change_leverage(symbol=symbol, leverage=leverage)
        return success_response(result, f"Leverage set to {leverage}x for {symbol}")
    except BinanceAPIException as e:
        logger.error(f"set_leverage error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"set_leverage error: {e}")
        return error_response(str(e))


@mcp.tool()
def binance_get_open_orders(market_type: str = "futures", symbol: str = "") -> str:
    """
    Get all open (pending) orders.

    Args:
        market_type: "spot" or "futures".
        symbol:      Specific symbol, or empty for all.
    """
    try:
        market_type = market_type.lower()
        params = {}
        if symbol:
            params["symbol"] = symbol.upper()

        if market_type == "futures":
            orders = client.futures_get_open_orders(**params)
        else:
            orders = client.get_open_orders(**params)

        return success_response(orders, f"{len(orders)} open order(s)")
    except BinanceAPIException as e:
        logger.error(f"get_open_orders error: {e}")
        return error_response(f"Binance API error: {e.message}", {"code": e.code})
    except Exception as e:
        logger.error(f"get_open_orders error: {e}")
        return error_response(str(e))


# ═══════════════════════════════════════════════════════════════════════════
#  Entry point
# ═══════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    logger.info("Starting Binance MCP Server")
    mcp.run(transport="stdio")
