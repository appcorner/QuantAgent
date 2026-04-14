#!/usr/bin/env python3
"""
QuantAgent automatic trading runner.

Features:
- Reads symbols, providers, and timeframes from config.json
- Runs QuantAgent analysis on each scheduled symbol
- Checks balances and current positions before placing orders
- Records history and win/loss statistics
- Writes status reports after each cycle
- Waits until the next timeframe boundary automatically

Safety:
- dry_run defaults to True in config.json
- Spot markets do not open SHORT positions; they can only flatten/sell
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import hmac
import importlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:
    requests = None

try:
    load_dotenv = importlib.import_module("dotenv").load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv(".env")

TIMEFRAME_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
    "1w": 604800,
}

KNOWN_QUOTES = ("USDT", "USDC", "FDUSD", "BUSD", "BTC", "ETH", "BNB", "THB", "USD")
BITKUB_BASE_URL = "https://api.bitkub.com"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def split_symbol(symbol: str) -> tuple[str, str]:
    if "_" in symbol:
        base, quote = symbol.split("_", 1)
        return base.upper(), quote.upper()
    upper = symbol.upper()
    for quote in KNOWN_QUOTES:
        if upper.endswith(quote) and len(upper) > len(quote):
            return upper[: -len(quote)], quote
    return upper, ""


def parse_risk_reward(value: Any) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "")
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if not nums:
        return 0.0
    if len(nums) >= 2 and ":" in text:
        right = safe_float(nums[1], 0.0)
        return right if right > 0 else safe_float(nums[0], 0.0)
    return safe_float(nums[0], 0.0)


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def timeframe_to_seconds(timeframe: str) -> int:
    tf = str(timeframe).strip().lower()
    if tf not in TIMEFRAME_SECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    return TIMEFRAME_SECONDS[tf]


def seconds_until_next_boundary(timeframe: str, now_ts: float | None = None) -> int:
    now_ts = time.time() if now_ts is None else now_ts
    tf_seconds = timeframe_to_seconds(timeframe)
    remainder = int(now_ts) % tf_seconds
    wait = tf_seconds - remainder if remainder else tf_seconds
    return max(1, wait)


class RuntimeStore:
    def __init__(self, history_file: Path, state_file: Path, status_file: Path):
        self.history_file = history_file
        self.state_file = state_file
        self.status_file = status_file

    def load_state(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                pass
        return {
            "last_slots": {},
            "open_trades": {},
            "summary": {"wins": 0, "losses": 0, "breakeven": 0, "closed": 0},
        }

    def save_state(self, state: dict[str, Any]) -> None:
        ensure_parent(self.state_file)
        self.state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

    def write_status(self, payload: dict[str, Any]) -> None:
        ensure_parent(self.status_file)
        self.status_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

    def append_history(self, event: dict[str, Any]) -> None:
        ensure_parent(self.history_file)
        fieldnames = [
            "timestamp",
            "provider",
            "symbol",
            "timeframe",
            "market_type",
            "event",
            "decision",
            "action",
            "status",
            "price",
            "quantity",
            "confidence_score",
            "risk_reward_ratio",
            "outcome",
            "pnl",
            "dry_run",
            "notes",
        ]
        row = {key: self._serialize(event.get(key, "")) for key in fieldnames}
        exists = self.history_file.exists()
        with self.history_file.open("a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    @staticmethod
    def _serialize(value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return value


class BaseExchangeAdapter:
    provider_name = "base"

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int):
        raise NotImplementedError

    def get_balance_snapshot(self, item: dict[str, Any]) -> Any:
        return {}

    def get_positions(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def place_order(self, item: dict[str, Any], decision: str, price: float) -> dict[str, Any]:
        raise NotImplementedError

    def close_position(self, item: dict[str, Any], existing_positions: list[dict[str, Any]], price: float) -> dict[str, Any]:
        raise NotImplementedError


class BinanceExchangeAdapter(BaseExchangeAdapter):
    provider_name = "binance"

    def __init__(self):
        try:
            BinanceTradeClient = importlib.import_module("binance.client").Client
            BinanceAPIClient = importlib.import_module("binance_data").BinanceAPIClient
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Binance support requires the python-binance package. Install project dependencies first."
            ) from exc

        self.market_client = BinanceAPIClient()
        self.trade_client = BinanceTradeClient(
            os.environ.get("BINANCE_API_KEY", ""),
            os.environ.get("BINANCE_API_SECRET", ""),
        )

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int):
        return self.market_client.fetch_ohlc(symbol, timeframe, count=bars)

    def get_balance_snapshot(self, item: dict[str, Any]) -> Any:
        market_type = str(item.get("market_type", "spot")).lower()
        try:
            if market_type == "futures":
                return self.trade_client.futures_account_balance()
            account = self.trade_client.get_account()
            return [b for b in account.get("balances", []) if safe_float(b.get("free")) > 0 or safe_float(b.get("locked")) > 0]
        except Exception as exc:
            return {"error": str(exc)}

    def get_positions(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        symbol = str(item["symbol"]).upper()
        market_type = str(item.get("market_type", "spot")).lower()
        try:
            if market_type == "futures":
                positions = self.trade_client.futures_position_information(symbol=symbol)
                active = []
                for pos in positions:
                    amt = safe_float(pos.get("positionAmt"))
                    if amt == 0:
                        continue
                    active.append(
                        {
                            "symbol": symbol,
                            "side": "LONG" if amt > 0 else "SHORT",
                            "quantity": abs(amt),
                            "entry_price": safe_float(pos.get("entryPrice")),
                            "raw": pos,
                        }
                    )
                return active

            balances = self.trade_client.get_account().get("balances", [])
            base_asset, _ = split_symbol(symbol)
            for bal in balances:
                if bal.get("asset", "").upper() == base_asset:
                    qty = safe_float(bal.get("free"))
                    if qty > 0:
                        return [{"symbol": symbol, "side": "LONG", "quantity": qty, "entry_price": 0.0, "raw": bal}]
            return []
        except Exception:
            return []

    def place_order(self, item: dict[str, Any], decision: str, price: float) -> dict[str, Any]:
        symbol = str(item["symbol"]).upper()
        market_type = str(item.get("market_type", "spot")).lower()
        decision = decision.upper()

        if market_type == "spot" and decision == "SHORT":
            return {"status": "skipped", "reason": "Binance spot cannot open SHORT positions."}

        quantity = self._resolve_quantity(item, price)
        side = "BUY" if decision == "LONG" else "SELL"
        if quantity <= 0:
            return {"status": "skipped", "reason": "Quantity resolved to zero."}

        if normalize_bool(item.get("dry_run_override"), False):
            return {"status": "dry_run", "reason": "Dry run override active.", "quantity": quantity, "side": side}

        try:
            if market_type == "futures":
                result = self.trade_client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
            else:
                result = self.trade_client.create_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
            return {"status": "success", "quantity": quantity, "side": side, "result": result}
        except Exception as exc:
            return {"status": "error", "reason": str(exc), "quantity": quantity, "side": side}

    def close_position(self, item: dict[str, Any], existing_positions: list[dict[str, Any]], price: float) -> dict[str, Any]:
        symbol = str(item["symbol"]).upper()
        market_type = str(item.get("market_type", "spot")).lower()
        if not existing_positions:
            return {"status": "skipped", "reason": "No open position to close."}

        pos = existing_positions[0]
        quantity = safe_float(pos.get("quantity"))
        if quantity <= 0:
            return {"status": "skipped", "reason": "Position quantity is zero."}

        side = "SELL" if pos.get("side") == "LONG" else "BUY"
        try:
            if market_type == "futures":
                result = self.trade_client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=quantity, reduceOnly=True)
            else:
                result = self.trade_client.create_order(symbol=symbol, side="SELL", type="MARKET", quantity=quantity)
            return {"status": "success", "side": side, "quantity": quantity, "result": result}
        except Exception as exc:
            return {"status": "error", "reason": str(exc), "side": side, "quantity": quantity}

    @staticmethod
    def _resolve_quantity(item: dict[str, Any], price: float) -> float:
        qty = safe_float(item.get("quantity"))
        if qty > 0:
            return round(qty, 6)
        quote_amount = safe_float(item.get("quote_amount"))
        if quote_amount > 0 and price > 0:
            return round(quote_amount / price, 6)
        return 0.0


class BitkubExchangeAdapter(BaseExchangeAdapter):
    provider_name = "bitkub"

    def __init__(self):
        if requests is None:
            raise RuntimeError("Bitkub support requires the requests package. Install project dependencies first.")
        BitkubClient = importlib.import_module("bitkub_data").BitkubClient

        self.market_client = BitkubClient()
        self.api_key = os.environ.get("BITKUB_API_KEY", "")
        self.api_secret = os.environ.get("BITKUB_API_SECRET", "")

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int):
        return self.market_client.fetch_ohlc(symbol, timeframe, count=bars)

    def get_balance_snapshot(self, item: dict[str, Any]) -> Any:
        try:
            data = self._signed_post("/api/v3/market/balances")
            return data.get("result", {})
        except Exception as exc:
            return {"error": str(exc)}

    def get_positions(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        symbol = str(item["symbol"]).upper()
        base_asset, _ = split_symbol(symbol)
        try:
            balances = self._signed_post("/api/v3/market/balances").get("result", {})
            info = balances.get(base_asset, {})
            qty = safe_float(info.get("available"))
            if qty > 0:
                return [{"symbol": symbol, "side": "LONG", "quantity": qty, "entry_price": 0.0, "raw": info}]
            return []
        except Exception:
            return []

    def place_order(self, item: dict[str, Any], decision: str, price: float) -> dict[str, Any]:
        symbol = str(item["symbol"]).lower()
        decision = decision.upper()
        if decision == "SHORT":
            return {"status": "skipped", "reason": "Bitkub spot cannot open SHORT positions."}

        quote_amount = safe_float(item.get("quote_amount"))
        if quote_amount <= 0:
            quantity = safe_float(item.get("quantity"))
            quote_amount = quantity * price
        if quote_amount <= 0:
            return {"status": "skipped", "reason": "Set quote_amount or quantity in config for Bitkub buy orders."}

        try:
            result = self._signed_post(
                "/api/v3/market/place-bid",
                {"sym": symbol, "amt": round(quote_amount, 2), "rat": 0, "typ": "market"},
            )
            return {"status": "success", "quantity": round(quote_amount, 2), "side": "BUY", "result": result.get("result", result)}
        except Exception as exc:
            return {"status": "error", "reason": str(exc), "quantity": round(quote_amount, 2), "side": "BUY"}

    def close_position(self, item: dict[str, Any], existing_positions: list[dict[str, Any]], price: float) -> dict[str, Any]:
        symbol = str(item["symbol"]).lower()
        if not existing_positions:
            return {"status": "skipped", "reason": "No spot holding to sell."}
        quantity = safe_float(existing_positions[0].get("quantity"))
        if quantity <= 0:
            return {"status": "skipped", "reason": "Position quantity is zero."}
        try:
            result = self._signed_post(
                "/api/v3/market/place-ask",
                {"sym": symbol, "amt": quantity, "rat": 0, "typ": "market"},
            )
            return {"status": "success", "quantity": quantity, "side": "SELL", "result": result.get("result", result)}
        except Exception as exc:
            return {"status": "error", "reason": str(exc), "quantity": quantity, "side": "SELL"}

    def _get_server_time(self) -> str:
        resp = requests.get(f"{BITKUB_BASE_URL}/api/v3/servertime", timeout=15)
        resp.raise_for_status()
        return str(resp.json())

    def _sign(self, timestamp: str, method: str, path: str, body: str = "") -> str:
        payload = f"{timestamp}{method}{path}{body}"
        return hmac.new(self.api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    def _signed_post(self, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.api_key or not self.api_secret:
            raise RuntimeError("BITKUB_API_KEY or BITKUB_API_SECRET is missing.")
        body_str = json.dumps(body or {})
        ts = self._get_server_time()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-BTK-APIKEY": self.api_key,
            "X-BTK-TIMESTAMP": ts,
            "X-BTK-SIGN": self._sign(ts, "POST", path, body_str),
        }
        resp = requests.post(f"{BITKUB_BASE_URL}{path}", headers=headers, data=body_str, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and data.get("error") not in (0, None):
            raise RuntimeError(f"Bitkub API error: {data}")
        return data


class MT5ExchangeAdapter(BaseExchangeAdapter):
    provider_name = "mt5"

    def __init__(self):
        if requests is None:
            raise RuntimeError("MT5 support requires the requests package. Install project dependencies first.")
        MT5BridgeClient = importlib.import_module("mt5_data").MT5BridgeClient

        self.client = MT5BridgeClient()
        self.base_url = self.client.base_url
        self.timeout = self.client.timeout

    def fetch_ohlc(self, symbol: str, timeframe: str, bars: int):
        return self.client.fetch_ohlc(symbol, timeframe, count=bars)

    def get_balance_snapshot(self, item: dict[str, Any]) -> Any:
        try:
            resp = requests.get(f"{self.base_url}/account", timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as exc:
            return {"error": str(exc)}

    def get_positions(self, item: dict[str, Any]) -> list[dict[str, Any]]:
        symbol = str(item["symbol"]).upper()
        try:
            resp = requests.get(f"{self.base_url}/positions", params={"symbols": symbol}, timeout=self.timeout)
            resp.raise_for_status()
            positions = resp.json()
            normalized = []
            for pos in positions or []:
                side = str(pos.get("type") or pos.get("side") or "").upper()
                if side in {"0", "BUY"}:
                    norm_side = "LONG"
                else:
                    norm_side = "SHORT"
                normalized.append(
                    {
                        "symbol": symbol,
                        "side": norm_side,
                        "quantity": safe_float(pos.get("volume") or pos.get("lots"), 0.0),
                        "entry_price": safe_float(pos.get("price_open") or pos.get("entry_price"), 0.0),
                        "ticket": pos.get("ticket"),
                        "raw": pos,
                    }
                )
            return normalized
        except Exception:
            return []

    def place_order(self, item: dict[str, Any], decision: str, price: float) -> dict[str, Any]:
        symbol = str(item["symbol"]).upper()
        volume = safe_float(item.get("lot") or item.get("volume"), 0.0)
        if volume <= 0:
            return {"status": "skipped", "reason": "Set lot or volume in config for MT5 orders."}

        side = "BUY" if decision.upper() == "LONG" else "SELL"
        sl = safe_float(item.get("sl", item.get("stop_loss", 0.0)), 0.0)
        tp = safe_float(item.get("tp", item.get("take_profit", 0.0)), 0.0)
        comment = str(item.get("comment", "QuantAgent auto trader"))
        magic = int(item.get("magic", 123456))

        payload = {
            "symbol": symbol,
            "type": side,
            "volume": volume,
            "sl": sl,
            "tp": tp,
            "comment": comment,
            "magic": magic,
        }
        try:
            resp = requests.post(f"{self.base_url}/order", json=payload, timeout=self.timeout)
            resp.raise_for_status()
            return {"status": "success", "quantity": volume, "side": side, "result": resp.json()}
        except Exception as exc:
            return {"status": "error", "reason": str(exc), "quantity": volume, "side": side}

    def close_position(self, item: dict[str, Any], existing_positions: list[dict[str, Any]], price: float) -> dict[str, Any]:
        if not existing_positions:
            return {"status": "skipped", "reason": "No MT5 position to close."}
        results = []
        for pos in existing_positions:
            ticket = pos.get("ticket")
            if ticket is None:
                continue
            try:
                resp = requests.post(f"{self.base_url}/close", json={"ticket": ticket}, timeout=self.timeout)
                resp.raise_for_status()
                results.append({"ticket": ticket, "status": "closed", "detail": resp.json()})
            except Exception as exc:
                results.append({"ticket": ticket, "status": "error", "detail": str(exc)})
        if any(r.get("status") == "closed" for r in results):
            return {"status": "success", "quantity": len(results), "side": "CLOSE", "result": results}
        return {"status": "error", "reason": "Failed to close MT5 position(s).", "result": results}


class AutoTradingEngine:
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self.load_config(self.config_path)

        history_file = Path(self.config.get("history_file", "data/auto_trade_history.csv"))
        state_file = Path(self.config.get("state_file", "data/auto_trade_state.json"))
        status_file = Path(self.config.get("status_file", "data/auto_trade_status.json"))
        self.store = RuntimeStore(history_file=history_file, state_file=state_file, status_file=status_file)
        self.state = self.store.load_state()
        self._analyzer = None
        self.adapters: dict[str, BaseExchangeAdapter] = {}

    @staticmethod
    def load_config(path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("dry_run", True)
        data.setdefault("history_file", "data/auto_trade_history.csv")
        data.setdefault("state_file", "data/auto_trade_state.json")
        data.setdefault("status_file", "data/auto_trade_status.json")
        data.setdefault("risk", {})
        data.setdefault("symbols", [])
        data["risk"].setdefault("default_bars", 120)
        data["risk"].setdefault("min_confidence_score", 50)
        data["risk"].setdefault("min_risk_reward_ratio", 1.2)
        data["risk"].setdefault("allow_reentry_same_direction", False)
        data["risk"].setdefault("close_on_opposite_signal", True)
        data["risk"].setdefault("close_on_no_signal", False)
        return data

    def validate_config(self) -> list[str]:
        errors: list[str] = []
        enabled = [item for item in self.config.get("symbols", []) if normalize_bool(item.get("enabled", True), True)]
        if not enabled:
            errors.append("No enabled symbols found in config.json")
        for idx, item in enumerate(enabled, start=1):
            provider = str(item.get("provider", "")).lower()
            symbol = item.get("symbol")
            timeframe = str(item.get("timeframe", "")).lower()
            if provider not in {"binance", "bitkub", "mt5"}:
                errors.append(f"Item #{idx}: provider must be one of binance, bitkub, mt5")
            if not symbol:
                errors.append(f"Item #{idx}: symbol is required")
            if timeframe not in TIMEFRAME_SECONDS:
                errors.append(f"Item #{idx}: unsupported timeframe '{timeframe}'")
        return errors

    def _get_adapter(self, provider: str) -> BaseExchangeAdapter:
        provider = provider.lower()
        if provider not in self.adapters:
            if provider == "binance":
                self.adapters[provider] = BinanceExchangeAdapter()
            elif provider == "bitkub":
                self.adapters[provider] = BitkubExchangeAdapter()
            elif provider == "mt5":
                self.adapters[provider] = MT5ExchangeAdapter()
            else:
                raise ValueError(f"Unsupported provider: {provider}")
        return self.adapters[provider]

    def _get_analyzer(self):
        if self._analyzer is None:
            from trading_graph import TradingGraph
            from web_interface import WebTradingAnalyzer

            llm_cfg = self.config.get("llm", {})
            analyzer = WebTradingAnalyzer()
            analyzer.config.update(
                {
                    "agent_llm_provider": llm_cfg.get("provider", analyzer.config.get("agent_llm_provider", "openai")),
                    "graph_llm_provider": llm_cfg.get("provider", analyzer.config.get("graph_llm_provider", "openai")),
                    "agent_llm_model": llm_cfg.get("agent_model", analyzer.config.get("agent_llm_model")),
                    "graph_llm_model": llm_cfg.get("graph_model", analyzer.config.get("graph_llm_model")),
                    "agent_llm_temperature": llm_cfg.get("temperature", analyzer.config.get("agent_llm_temperature", 0.1)),
                    "graph_llm_temperature": llm_cfg.get("temperature", analyzer.config.get("graph_llm_temperature", 0.1)),
                }
            )
            analyzer.trading_graph = TradingGraph(config=analyzer.config)
            self._analyzer = analyzer
        return self._analyzer

    def run_once(self) -> dict[str, Any]:
        enabled_items = [item for item in self.config.get("symbols", []) if normalize_bool(item.get("enabled", True), True)]
        due_items = [item for item in enabled_items if self._is_due(item)]

        results = []
        for item in due_items:
            results.append(self._process_item(item))
            self.state["last_slots"][self._schedule_key(item)] = self._current_slot(item)

        next_wait = self._seconds_until_next_run(enabled_items)
        status_payload = {
            "timestamp": now_iso(),
            "dry_run": normalize_bool(self.config.get("dry_run"), True),
            "processed": len(due_items),
            "next_wait_seconds": next_wait,
            "results": results,
            "summary": self.state.get("summary", {}),
            "open_trades": self.state.get("open_trades", {}),
        }
        self.store.write_status(status_payload)
        self.store.save_state(self.state)
        return status_payload

    def run_forever(self) -> None:
        while True:
            status = self.run_once()
            processed = status.get("processed", 0)
            next_wait = status.get("next_wait_seconds", 60)
            summary = status.get("summary", {})
            print(
                f"[{status['timestamp']}] processed={processed} open={len(self.state.get('open_trades', {}))} "
                f"wins={summary.get('wins', 0)} losses={summary.get('losses', 0)} next_wait={next_wait}s"
            )
            time.sleep(next_wait)

    def _process_item(self, item: dict[str, Any]) -> dict[str, Any]:
        provider = str(item["provider"]).lower()
        symbol = str(item["symbol"])
        timeframe = str(item["timeframe"]).lower()
        market_type = str(item.get("market_type", "spot")).lower()
        bars = int(item.get("bars", self.config["risk"].get("default_bars", 120)))
        dry_run = normalize_bool(item.get("dry_run", self.config.get("dry_run", True)), True)

        balance: Any = {}
        existing_positions: list[dict[str, Any]] = []

        event: dict[str, Any] = {
            "timestamp": now_iso(),
            "provider": provider,
            "symbol": symbol,
            "timeframe": timeframe,
            "market_type": market_type,
            "event": "ANALYZE",
            "decision": "",
            "action": "",
            "status": "pending",
            "price": 0.0,
            "quantity": 0.0,
            "confidence_score": 0.0,
            "risk_reward_ratio": 0.0,
            "outcome": "",
            "pnl": "",
            "dry_run": dry_run,
            "notes": "",
        }

        try:
            adapter = self._get_adapter(provider)
            balance = adapter.get_balance_snapshot(item)
            live_positions = adapter.get_positions(item)
            self._sync_open_trades_with_live_positions(item, live_positions, clear_missing=not dry_run)
            existing_positions = self._effective_positions(item, live_positions)

            df = adapter.fetch_ohlc(symbol, timeframe, bars)
            if df is None or df.empty:
                event.update({"status": "error", "action": "skip", "notes": "No OHLC data returned."})
                self.store.append_history(event)
                return {**event, "balance": balance, "positions": existing_positions}

            last_price = safe_float(df["Close"].iloc[-1], 0.0)
            event["price"] = last_price

            analyzer = self._get_analyzer()
            results = analyzer.run_analysis(df, symbol, timeframe)
            formatted = analyzer.extract_analysis_results(results)
            decision_blob = formatted.get("final_decision", {}) or {}
            decision = str(decision_blob.get("decision", "")).upper().strip()
            should_enter = normalize_bool(decision_blob.get("should_enter_now"), True)
            confidence_score = safe_float(decision_blob.get("confidence_score"), 0.0)
            risk_reward_ratio = parse_risk_reward(decision_blob.get("risk_reward_ratio"))

            event["decision"] = decision or "UNKNOWN"
            event["confidence_score"] = confidence_score
            event["risk_reward_ratio"] = risk_reward_ratio

            if decision not in {"LONG", "SHORT"}:
                event.update({"status": "skipped", "action": "skip", "notes": "Decision output was not LONG/SHORT."})
                self.store.append_history(event)
                return {**event, "balance": balance, "positions": existing_positions, "analysis": formatted}

            min_conf = safe_float(item.get("min_confidence_score", self.config["risk"].get("min_confidence_score", 50)))
            min_rr = safe_float(item.get("min_risk_reward_ratio", self.config["risk"].get("min_risk_reward_ratio", 1.2)))
            if confidence_score and confidence_score < min_conf:
                event.update({"status": "skipped", "action": "skip", "notes": f"Confidence {confidence_score} is below threshold {min_conf}."})
                self.store.append_history(event)
                return {**event, "balance": balance, "positions": existing_positions, "analysis": formatted}
            if risk_reward_ratio and risk_reward_ratio < min_rr:
                event.update({"status": "skipped", "action": "skip", "notes": f"Risk/reward {risk_reward_ratio} is below threshold {min_rr}."})
                self.store.append_history(event)
                return {**event, "balance": balance, "positions": existing_positions, "analysis": formatted}

            trade_key = self._trade_key(item)
            current_side = existing_positions[0]["side"] if existing_positions else None

            if existing_positions and current_side == decision and not normalize_bool(self.config["risk"].get("allow_reentry_same_direction"), False):
                event.update({"status": "ok", "action": "hold", "notes": f"Existing {current_side} position already open."})
                self.store.append_history(event)
                return {**event, "balance": balance, "positions": existing_positions, "analysis": formatted}

            if existing_positions and current_side != decision and normalize_bool(self.config["risk"].get("close_on_opposite_signal"), True):
                close_result = {"status": "dry_run", "reason": "Dry run close."} if dry_run else adapter.close_position(item, existing_positions, last_price)
                self._close_tracked_trade(trade_key, last_price, f"Opposite signal: {decision}")
                event.update({"event": "CLOSE", "action": "close", "status": close_result.get("status", "unknown"), "notes": close_result.get("reason", "Closed on opposite signal.")})
                self.store.append_history(event)

            if not should_enter:
                event.update({"status": "skipped", "action": "skip", "notes": "Decision advised not to enter now."})
                self.store.append_history(event)
                return {**event, "balance": balance, "positions": existing_positions, "analysis": formatted}

            if dry_run:
                order_result = {"status": "dry_run", "quantity": self._preview_quantity(item, last_price), "side": "BUY" if decision == "LONG" else "SELL", "reason": "Dry run mode enabled."}
            else:
                order_result = adapter.place_order(item, decision, last_price)

            event.update(
                {
                    "event": "OPEN",
                    "action": "open",
                    "status": order_result.get("status", "unknown"),
                    "quantity": order_result.get("quantity", 0.0),
                    "notes": order_result.get("reason", "Order processed."),
                }
            )

            if order_result.get("status") in {"success", "dry_run"}:
                self.state.setdefault("open_trades", {})[trade_key] = {
                    "provider": provider,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "market_type": market_type,
                    "decision": decision,
                    "entry_price": last_price,
                    "quantity": order_result.get("quantity", 0.0),
                    "opened_at": now_iso(),
                }

            self.store.append_history(event)
            return {**event, "balance": balance, "positions": existing_positions, "analysis": formatted}

        except Exception as exc:
            event.update({"status": "error", "action": "skip", "notes": str(exc)})
            self.store.append_history(event)
            return {**event, "balance": balance, "positions": existing_positions}

    def _close_tracked_trade(self, trade_key: str, close_price: float, reason: str) -> None:
        trade = self.state.setdefault("open_trades", {}).pop(trade_key, None)
        if not trade:
            return

        entry = safe_float(trade.get("entry_price"), 0.0)
        qty = safe_float(trade.get("quantity"), 0.0)
        decision = str(trade.get("decision", "LONG")).upper()
        pnl = ((close_price - entry) * qty) if decision == "LONG" else ((entry - close_price) * qty)
        outcome = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAKEVEN"

        summary = self.state.setdefault("summary", {"wins": 0, "losses": 0, "breakeven": 0, "closed": 0})
        if outcome == "WIN":
            summary["wins"] = summary.get("wins", 0) + 1
        elif outcome == "LOSS":
            summary["losses"] = summary.get("losses", 0) + 1
        else:
            summary["breakeven"] = summary.get("breakeven", 0) + 1
        summary["closed"] = summary.get("closed", 0) + 1

        self.store.append_history(
            {
                "timestamp": now_iso(),
                "provider": trade.get("provider", ""),
                "symbol": trade.get("symbol", ""),
                "timeframe": trade.get("timeframe", ""),
                "market_type": trade.get("market_type", ""),
                "event": "RESULT",
                "decision": decision,
                "action": "closed",
                "status": "closed",
                "price": close_price,
                "quantity": qty,
                "confidence_score": "",
                "risk_reward_ratio": "",
                "outcome": outcome,
                "pnl": round(pnl, 6),
                "dry_run": self.config.get("dry_run", True),
                "notes": reason,
            }
        )

    def _sync_open_trades_with_live_positions(
        self,
        item: dict[str, Any],
        live_positions: list[dict[str, Any]],
        clear_missing: bool = True,
    ) -> None:
        trade_key = self._trade_key(item)
        open_trades = self.state.setdefault("open_trades", {})

        if not live_positions:
            if clear_missing:
                open_trades.pop(trade_key, None)
            return

        long_positions = [p for p in live_positions if str(p.get("side", "")).upper() == "LONG"]
        short_positions = [p for p in live_positions if str(p.get("side", "")).upper() == "SHORT"]

        long_qty = sum(safe_float(p.get("quantity"), 0.0) for p in long_positions)
        short_qty = sum(safe_float(p.get("quantity"), 0.0) for p in short_positions)

        if long_qty == short_qty:
            open_trades.pop(trade_key, None)
            return

        dominant_positions = long_positions if long_qty > short_qty else short_positions
        decision = "LONG" if long_qty > short_qty else "SHORT"
        quantity = abs(long_qty - short_qty)

        weighted_notional = sum(
            safe_float(pos.get("entry_price"), 0.0) * safe_float(pos.get("quantity"), 0.0)
            for pos in dominant_positions
        )
        weighted_qty = sum(safe_float(pos.get("quantity"), 0.0) for pos in dominant_positions)
        entry_price = (weighted_notional / weighted_qty) if weighted_qty > 0 else 0.0

        existing = open_trades.get(trade_key, {})
        open_trades[trade_key] = {
            "provider": item.get("provider"),
            "symbol": item.get("symbol"),
            "timeframe": item.get("timeframe"),
            "market_type": item.get("market_type", "spot"),
            "decision": decision,
            "entry_price": entry_price,
            "quantity": quantity,
            "opened_at": existing.get("opened_at", now_iso()),
            "source": "live_sync",
        }

    def _effective_positions(self, item: dict[str, Any], live_positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if live_positions:
            return live_positions
        trade = self.state.setdefault("open_trades", {}).get(self._trade_key(item))
        if trade:
            return [
                {
                    "symbol": trade.get("symbol"),
                    "side": trade.get("decision"),
                    "quantity": trade.get("quantity", 0.0),
                    "entry_price": trade.get("entry_price", 0.0),
                    "raw": {"source": trade.get("source", "state")},
                }
            ]
        return []

    def _preview_quantity(self, item: dict[str, Any], price: float) -> float:
        provider = str(item.get("provider", "")).lower()
        if provider == "binance":
            return BinanceExchangeAdapter._resolve_quantity(item, price)
        if provider == "bitkub":
            quote_amount = safe_float(item.get("quote_amount"))
            if quote_amount > 0:
                return round(quote_amount, 2)
            quantity = safe_float(item.get("quantity"))
            return round(quantity * price, 2) if quantity > 0 and price > 0 else 0.0
        if provider == "mt5":
            return safe_float(item.get("lot") or item.get("volume"), 0.0)
        return 0.0

    def _schedule_key(self, item: dict[str, Any]) -> str:
        return f"{item.get('provider')}:{item.get('symbol')}:{item.get('timeframe')}"

    def _trade_key(self, item: dict[str, Any]) -> str:
        return f"{item.get('provider')}:{item.get('symbol')}:{item.get('market_type', 'spot')}"

    def _current_slot(self, item: dict[str, Any]) -> int:
        tf_seconds = timeframe_to_seconds(str(item.get("timeframe", "1h")))
        return int(time.time() // tf_seconds)

    def _is_due(self, item: dict[str, Any]) -> bool:
        slot = self._current_slot(item)
        last_slot = self.state.setdefault("last_slots", {}).get(self._schedule_key(item))
        return last_slot != slot

    def _seconds_until_next_run(self, items: list[dict[str, Any]]) -> int:
        if not items:
            return 60
        waits = [seconds_until_next_boundary(str(item.get("timeframe", "1h"))) for item in items]
        return max(1, min(waits))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run QuantAgent in automatic trading mode.")
    parser.add_argument("--config", default="config.json", help="Path to config.json")
    parser.add_argument("--once", action="store_true", help="Run a single cycle and exit")
    parser.add_argument("--validate-config", action="store_true", help="Validate config.json and exit")
    parser.add_argument("--show-status", action="store_true", help="Print the last saved status report and exit")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    engine = AutoTradingEngine(config_path=args.config)

    if args.validate_config:
        errors = engine.validate_config()
        if errors:
            print("Config validation failed:")
            for err in errors:
                print(f"- {err}")
            return 1
        print("Config validation passed.")
        return 0

    if args.show_status:
        status_path = Path(engine.config.get("status_file", "data/auto_trade_status.json"))
        if not status_path.exists():
            print("No status report found yet.")
            return 0
        print(status_path.read_text(encoding="utf-8"))
        return 0

    errors = engine.validate_config()
    if errors:
        print("Config validation failed:")
        for err in errors:
            print(f"- {err}")
        return 1

    if args.once:
        status = engine.run_once()
        print(json.dumps(status, indent=2, ensure_ascii=False, default=str))
        return 0

    engine.run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
