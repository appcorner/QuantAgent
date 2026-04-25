#!/usr/bin/env python3
"""
MT5 Adaptive Trailing Stop Lock (ATL) Daemon

Monitors live MT5 positions and progressively locks profits using stage-based logic:
- Born BE: Profit >= 5 USD → Lock 1 USD
- Pre BE: Profit >= 20 USD → Lock 5 USD
- BE: Profit >= 50 USD → Lock 30 USD
- TL: Profit >= 70 USD → Lock 50 USD
- TP Trail: Profit >= 80 USD → Lock 60 USD + High Track + Remove Fixed TP

Features:
- Continuous polling of MT5 bridge (every N seconds)
- High-water mark tracking (best_profit_usd)
- Stage progression with one-time notifications
- Dynamic SL modification based on locked profit
- Retrace detection and auto-close on 30% drawdown
- State persistence (JSON) and event logging (JSONL)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
except ModuleNotFoundError:
    requests = None

try:
    load_dotenv = __import__("importlib").import_module("dotenv").load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

load_dotenv(".env")


STAGE_ORDER = ["below_born_be", "born_be", "pre_be", "be", "tl", "tp_trail"]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def now_iso() -> str:
    return utc_now().isoformat()


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def profit_per_price_unit(entry_price: float, mark_price: float, profit_usd: float) -> float:
    """Estimate USD profit per 1.0 price move from live position snapshot."""
    price_move = abs(safe_float(mark_price) - safe_float(entry_price))
    if price_move <= 0:
        return 0.0
    return abs(safe_float(profit_usd)) / price_move


def setup_logging(log_level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger("mt5_adaptive_tl")
    logger.setLevel(getattr(logging, log_level.upper()))
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger


class AdaptiveTLState:
    """Manages state for a single tracked MT5 position."""

    def __init__(self, symbol: str, state_dir: Path = Path("runtime/adaptive_tl")):
        self.symbol = symbol
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / f"{symbol}.json"
        self.events_file = self.state_dir / f"{symbol}_events.jsonl"
        self.data = self._load()

    def _load(self) -> dict[str, Any]:
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return self._default_state()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "ticket": None,
            "side": None,
            "entry_price": 0.0,
            "current_price": 0.0,
            "current_profit_usd": 0.0,
            "best_profit_usd": 0.0,
            "best_price": 0.0,
            "current_sl": 0.0,
            "current_tp": 0.0,
            "current_stage": "below_born_be",
            "stage_unlocked": False,
            "locked_profit_usd": 0.0,
            "dynamic_lock_follow": False,
            "high_track_active": False,
            "last_updated": now_iso(),
            "opened_at": now_iso(),
        }

    def save(self) -> None:
        self.data["last_updated"] = now_iso()
        self.state_file.write_text(
            json.dumps(self.data, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def log_event(self, event_type: str, details: dict[str, Any] | None = None) -> None:
        event = {
            "timestamp": now_iso(),
            "symbol": self.symbol,
            "event_type": event_type,
            "details": details or {},
            "current_stage": self.data.get("current_stage"),
            "best_profit_usd": self.data.get("best_profit_usd"),
        }
        with self.events_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def reset_for_new_position(self, ticket: str, side: str, entry_price: float) -> None:
        self.data = self._default_state()
        self.data.update({
            "ticket": ticket,
            "side": side,
            "entry_price": entry_price,
            "opened_at": now_iso(),
        })
        self.save()
        self.log_event("position_reset", {
            "ticket": ticket,
            "side": side,
            "entry_price": entry_price,
        })


class AdaptiveTLEngine:
    """Manages ATL logic for all tracked MT5 positions."""

    def __init__(self, config: dict[str, Any], mt5_bridge_url: str | None = None, logger: logging.Logger | None = None):
        self.config = config
        self.logger = logger or setup_logging()
        self.atl_cfg = config.get("adaptive_tl", {})
        self.poll_interval = self.atl_cfg.get("poll_interval_seconds", 5)
        self.profit_stages = self.atl_cfg.get("profit_stages", {})
        self.retrace_pct = self.atl_cfg.get("high_track_retrace_pct", 30)
        self.enable_below_born_be_keep_distance = self.atl_cfg.get("below_born_be_keep_distance_enabled", True)
        self.state_dir = Path(self.atl_cfg.get("state_dir", "runtime/adaptive_tl"))
        self.dry_run = config.get("dry_run", True)

        env_mt5_bridge = os.environ.get("MT5_BRIDGE_URL", "").strip()
        self.mt5_bridge_url = (mt5_bridge_url or env_mt5_bridge or "http://localhost:5000").rstrip("/")
        self.http_timeout = safe_float(self.atl_cfg.get("bridge_timeout_seconds", 10), 10.0)

    def fetch_position_from_mt5(self, symbol: str) -> dict[str, Any] | None:
        """Fetch live position from MT5 bridge."""
        try:
            resp = requests.get(
                f"{self.mt5_bridge_url}/positions",
                params={"symbols": symbol},
                timeout=self.http_timeout
            )
            resp.raise_for_status()
            positions = resp.json()
            if positions and len(positions) > 0:
                return positions[0]
        except Exception as e:
            self.logger.error(f"Failed to fetch position for {symbol}: {e}")
        return None

    def modify_position_sl_tp(
        self,
        ticket: str,
        new_sl: float,
        new_tp: float
    ) -> bool:
        """Modify SL/TP via MT5 bridge."""
        try:
            payload = {
                "ticket": int(safe_float(ticket, 0.0)),
                "sl": safe_float(new_sl, 0.0),
                "tp": safe_float(new_tp, 0.0),
                "update_sl": safe_float(new_sl, 0.0) > 0,
                "update_tp": safe_float(new_tp, 0.0) > 0,
            }
            resp = requests.post(
                f"{self.mt5_bridge_url}/modify",
                json=payload,
                timeout=self.http_timeout
            )
            resp.raise_for_status()
            self.logger.info(f"Modified ticket {ticket}: SL={new_sl}, TP={new_tp}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to modify ticket {ticket}: {e}")
            return False

    def close_position(self, ticket: str) -> bool:
        """Close position via MT5 bridge."""
        try:
            resp = requests.post(
                f"{self.mt5_bridge_url}/close",
                json={"ticket": ticket},
                timeout=self.http_timeout
            )
            resp.raise_for_status()
            self.logger.info(f"Closed ticket {ticket}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to close ticket {ticket}: {e}")
            return False

    def determine_stage(self, current_profit_usd: float) -> str:
        """Determine profit stage based on thresholds."""
        tp_trail = self.profit_stages.get("tp_trail", {})
        tl = self.profit_stages.get("tl", {})
        be = self.profit_stages.get("be", {})
        pre_be = self.profit_stages.get("pre_be", {})
        born_be = self.profit_stages.get("born_be", {})

        if current_profit_usd >= tp_trail.get("trigger_usd", 80):
            return "tp_trail"
        elif current_profit_usd >= tl.get("trigger_usd", 70):
            return "tl"
        elif current_profit_usd >= be.get("trigger_usd", 50):
            return "be"
        elif current_profit_usd >= pre_be.get("trigger_usd", 20):
            return "pre_be"
        elif current_profit_usd >= born_be.get("trigger_usd", 5):
            return "born_be"
        else:
            return "below_born_be"

    def get_lock_target_for_stage(self, stage: str) -> float:
        """Get locked profit target USD for current stage."""
        stage_cfg = self.profit_stages.get(stage, {})
        return safe_float(stage_cfg.get("lock_usd", 0.0))

    def convert_locked_profit_to_sl(
        self,
        side: str,
        entry_price: float,
        current_price: float,
        locked_profit_usd: float,
        current_profit_usd: float,
    ) -> float:
        """Convert locked profit (USD) to SL price."""
        pppu = profit_per_price_unit(entry_price, current_price, current_profit_usd)
        if pppu <= 0:
            return entry_price

        protected_price_move = safe_float(locked_profit_usd, 0.0) / pppu
        if protected_price_move <= 0:
            return entry_price
        
        if side == "BUY":
            sl = entry_price + protected_price_move
        else:  # SELL
            sl = entry_price - protected_price_move
        
        return round(sl, 8)

    def calculate_dynamic_lock_from_best(
        self,
        side: str,
        entry_price: float,
        best_price: float,
        best_profit_usd: float,
        current_price: float,
    ) -> float:
        """Calculate dynamic SL from best profit achieved."""
        pppu = profit_per_price_unit(entry_price, best_price, best_profit_usd)
        if pppu <= 0:
            return entry_price

        protected_price_move = safe_float(best_profit_usd, 0.0) / pppu
        if protected_price_move <= 0:
            return entry_price
        
        if side == "BUY":
            sl = entry_price + protected_price_move
        else:  # SELL
            sl = entry_price - protected_price_move

        # Broker-side sanity checks to avoid invalid stops.
        if side == "BUY" and sl >= current_price:
            return entry_price
        if side == "SELL" and sl <= current_price:
            return entry_price
        
        return round(sl, 8)

    def should_close_on_retrace(
        self,
        best_profit_usd: float,
        current_profit_usd: float
    ) -> bool:
        """Check if position should close due to retrace."""
        if best_profit_usd <= 0:
            return False
        
        retrace_amount = best_profit_usd - current_profit_usd
        retrace_pct = (retrace_amount / best_profit_usd) * 100
        
        return retrace_pct >= self.retrace_pct

    def process_position(
        self,
        symbol: str,
        mt5_position: dict[str, Any] | None,
        state: AdaptiveTLState
    ) -> bool:
        """Process a single position through ATL logic. Returns True if position still active."""
        
        if mt5_position is None:
            self.logger.info(f"{symbol}: No position found on exchange")
            state.log_event("position_not_found", {})
            return False

        # Extract position data
        ticket = mt5_position.get("ticket")
        side_raw = str(mt5_position.get("type", mt5_position.get("side", ""))).upper()
        side = "BUY" if side_raw in {"0", "BUY"} else "SELL"
        entry_price = safe_float(mt5_position.get("price_open", mt5_position.get("entry_price")), 0.0)
        current_price = safe_float(mt5_position.get("price_current", mt5_position.get("current_price")), 0.0)
        current_sl = safe_float(mt5_position.get("sl", 0.0), 0.0)
        current_tp = safe_float(mt5_position.get("tp", 0.0), 0.0)
        profit = safe_float(mt5_position.get("profit", 0.0), 0.0)

        # Validate data
        if entry_price <= 0 or current_price <= 0:
            self.logger.error(f"{symbol}: Missing entry or current price")
            state.log_event("error_invalid_prices", {})
            return False

        if current_tp <= 0:
            self.logger.error(f"{symbol}: No TP set")
            state.log_event("error_no_tp", {})
            return False

        # Check TP direction
        if side == "BUY" and current_tp <= entry_price:
            self.logger.error(f"{symbol}: TP direction invalid for BUY")
            state.log_event("error_invalid_tp_direction", {})
            return False
        elif side == "SELL" and current_tp >= entry_price:
            self.logger.error(f"{symbol}: TP direction invalid for SELL")
            state.log_event("error_invalid_tp_direction", {})
            return False

        # Detect new position (ticket/side/entry changed)
        is_new_position = (
            state.data.get("ticket") != ticket
            or state.data.get("side") != side
            or abs(safe_float(state.data.get("entry_price"), 0.0) - entry_price) > 1e-6
        )

        if is_new_position:
            self.logger.info(f"{symbol}: New position detected. Resetting state.")
            state.reset_for_new_position(ticket, side, entry_price)

        # Update current profit and high-water mark
        current_profit_usd = profit
        best_profit_usd = state.data.get("best_profit_usd", 0.0)
        best_price = state.data.get("best_price", 0.0)
        prev_best_profit_usd = best_profit_usd
        prev_best_price = best_price
        has_new_best = False

        if current_profit_usd > best_profit_usd:
            best_profit_usd = current_profit_usd
            best_price = current_price
            has_new_best = True
            state.data["best_profit_usd"] = best_profit_usd
            state.data["best_price"] = best_price
            self.logger.info(f"{symbol}: New high-water mark: {best_profit_usd:.2f} USD")

        state.data["current_price"] = current_price
        state.data["current_profit_usd"] = current_profit_usd
        state.data["current_sl"] = current_sl
        state.data["current_tp"] = current_tp
        state.data["ticket"] = ticket

        # Determine current stage
        current_stage = self.determine_stage(current_profit_usd)
        prev_stage = state.data.get("current_stage", "below_born_be")
        stage_changed = current_stage != prev_stage

        if stage_changed:
            self.logger.info(f"{symbol}: Stage transition: {prev_stage} → {current_stage}")
            state.data["current_stage"] = current_stage
            state.data["stage_unlocked"] = False

        # Stage-based profit locking
        if current_stage != "below_born_be":
            lock_target = self.get_lock_target_for_stage(current_stage)
            
            if not state.data.get("stage_unlocked", False) and current_profit_usd >= lock_target:
                state.data["stage_unlocked"] = True
                state.data["locked_profit_usd"] = lock_target
                self.logger.info(f"{symbol}: Stage unlocked. Locking {lock_target:.2f} USD")
                state.log_event("stage_unlocked", {
                    "stage": current_stage,
                    "locked_profit_usd": lock_target,
                })
        
        # Calculate SL based on locked profit
        locked_profit = state.data.get("locked_profit_usd", 0.0)
        if locked_profit > 0:
            new_sl = self.convert_locked_profit_to_sl(
                side, entry_price, current_price, locked_profit, current_profit_usd
            )
            
            sl_improved = False
            if side == "BUY":
                sl_improved = new_sl > current_sl
            else:  # SELL
                sl_improved = new_sl < current_sl
            
            if sl_improved:
                if not self.dry_run:
                    success = self.modify_position_sl_tp(ticket, new_sl, current_tp)
                    if success:
                        state.log_event("sl_modified", {
                            "old_sl": current_sl,
                            "new_sl": new_sl,
                            "reason": f"Stage {current_stage} lock",
                        })
                        current_sl = new_sl
                else:
                    self.logger.info(f"{symbol}: [DRY RUN] Would modify SL: {current_sl} → {new_sl}")

        # Continuous high-water lock
        state.data["dynamic_lock_follow"] = False

        # For below_born_be stage, if profit makes a new high-water mark, shift SL by the
        # same price delta to preserve its distance from price.
        if (
            self.enable_below_born_be_keep_distance
            and current_stage == "below_born_be"
            and has_new_best
            and safe_float(current_sl, 0.0) > 0
            and safe_float(prev_best_profit_usd, 0.0) > 0
        ):
            if side == "BUY":
                price_delta = current_price - safe_float(prev_best_price, current_price)
                shifted_sl = round(current_sl + max(price_delta, 0.0), 8)
                sl_improved = shifted_sl > current_sl and shifted_sl < current_price
            else:  # SELL
                price_delta = safe_float(prev_best_price, current_price) - current_price
                shifted_sl = round(current_sl - max(price_delta, 0.0), 8)
                sl_improved = shifted_sl < current_sl and shifted_sl > current_price

            if sl_improved:
                if not self.dry_run:
                    success = self.modify_position_sl_tp(ticket, shifted_sl, current_tp)
                    if success:
                        state.data["dynamic_lock_follow"] = True
                        state.log_event("keep_distance_trail_follow", {
                            "old_sl": current_sl,
                            "new_sl": shifted_sl,
                            "best_profit_usd": best_profit_usd,
                            "reason": "below_born_be_keep_distance",
                        })
                        current_sl = shifted_sl
                else:
                    self.logger.info(f"{symbol}: [DRY RUN] Would shift SL (keep distance): {current_sl} → {shifted_sl}")

        if current_stage != "below_born_be" and best_profit_usd > 0:
            dynamic_sl = self.calculate_dynamic_lock_from_best(
                side, entry_price, best_price, best_profit_usd, current_price
            )
            
            sl_improved = False
            if side == "BUY":
                sl_improved = dynamic_sl > current_sl
            else:  # SELL
                sl_improved = dynamic_sl < current_sl
            
            if sl_improved:
                if not self.dry_run:
                    success = self.modify_position_sl_tp(ticket, dynamic_sl, current_tp)
                    if success:
                        state.data["dynamic_lock_follow"] = True
                        state.log_event("dynamic_lock_follow", {
                            "old_sl": current_sl,
                            "new_sl": dynamic_sl,
                            "best_profit_usd": best_profit_usd,
                        })
                        current_sl = dynamic_sl
                else:
                    self.logger.info(f"{symbol}: [DRY RUN] Would apply dynamic lock: {current_sl} → {dynamic_sl}")

        # High-track and retrace detection
        high_track_active = current_stage == "tp_trail" and state.data.get("high_track_active", False)
        
        if current_stage == "tp_trail" and not state.data.get("high_track_active", False):
            self.logger.info(f"{symbol}: Enabling high-track (TP Trail stage)")
            state.data["high_track_active"] = True
            state.log_event("high_track_enabled", {})
        
        if high_track_active:
            if self.should_close_on_retrace(best_profit_usd, current_profit_usd):
                self.logger.warning(
                    f"{symbol}: Retrace limit reached ({self.retrace_pct}%). "
                    f"Best: {best_profit_usd:.2f} USD, Current: {current_profit_usd:.2f} USD"
                )
                
                if not self.dry_run:
                    success = self.close_position(ticket)
                    if success:
                        state.log_event("position_closed_retrace", {
                            "best_profit_usd": best_profit_usd,
                            "current_profit_usd": current_profit_usd,
                            "retrace_pct": self.retrace_pct,
                        })
                        return False
                    else:
                        self.logger.error(f"{symbol}: Failed to close on retrace")
                        state.log_event("close_retrace_failed", {})
                else:
                    self.logger.info(f"{symbol}: [DRY RUN] Would close on retrace")
                    return False

        state.save()
        return True

    def run_once(self, symbols: list[str]) -> dict[str, Any]:
        """Run a single poll cycle for all symbols."""
        results = {}
        for symbol in symbols:
            state = AdaptiveTLState(symbol, self.state_dir)
            mt5_pos = self.fetch_position_from_mt5(symbol)
            
            try:
                still_active = self.process_position(symbol, mt5_pos, state)
                results[symbol] = {
                    "status": "active" if still_active else "closed",
                    "best_profit_usd": state.data.get("best_profit_usd", 0.0),
                    "current_stage": state.data.get("current_stage", "unknown"),
                }
            except Exception as e:
                self.logger.exception(f"Error processing {symbol}: {e}")
                results[symbol] = {"status": "error", "error": str(e)}
        
        return results

    def run_forever(self, symbols: list[str]) -> None:
        """Run continuous monitoring loop."""
        self.logger.info(f"Starting ATL monitoring for {len(symbols)} symbol(s): {symbols}")
        cycle = 0
        try:
            while True:
                cycle += 1
                self.logger.info(f"--- Cycle {cycle} ---")
                results = self.run_once(symbols)
                for symbol, result in results.items():
                    self.logger.info(f"{symbol}: {result}")
                self.logger.info(f"Sleeping {self.poll_interval}s...")
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.logger.info("Stopped by user.")


def load_config(path: str = "config.json") -> dict[str, Any]:
    """Load config from JSON file."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config not found: {config_path}")
    return json.loads(config_path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MT5 Adaptive Trailing Stop Lock daemon"
    )
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to config.json"
    )
    parser.add_argument(
        "--symbol",
        action="append",
        dest="symbols",
        help="Symbol to monitor (can specify multiple times)"
    )
    parser.add_argument(
        "--mt5-bridge",
        default=None,
        help="MT5 bridge base URL (override). If omitted, uses MT5_BRIDGE_URL from .env."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single cycle and exit"
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level"
    )
    
    args = parser.parse_args()
    
    logger = setup_logging(args.log_level)
    
    try:
        config = load_config(args.config)
        
        symbols = args.symbols or []
        if not symbols:
            raise ValueError("No symbols specified. Use --symbol SYMBOL (multiple allowed)")
        
        engine = AdaptiveTLEngine(config, mt5_bridge_url=args.mt5_bridge, logger=logger)
        
        if args.once:
            results = engine.run_once(symbols)
            print(json.dumps(results, indent=2, ensure_ascii=False, default=str))
            return 0
        
        engine.run_forever(symbols)
        return 0
    
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#build command for PyInstaller:
#uv run pyinstaller --onefile --clean --hidden-import dotenv --name "mt5-adaptive-tl" mt5_adaptive_tl.py