"""
MT5 Bridge Data Client

HTTP client module that connects to a mt5-bridge server
(https://github.com/akivajp/mt5-bridge) to fetch OHLC data from MetaTrader 5.

The server runs on Windows (where MT5 is installed) and this client
can run on any platform (Linux, macOS, Windows).

Returns DataFrames in the same format as fetch_yfinance_data() so they can
be passed directly to WebTradingAnalyzer.run_analysis().
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import pandas as pd
import requests

from dotenv import load_dotenv

load_dotenv(".env")


class MT5BridgeClient:
    """
    HTTP client for mt5-bridge REST API.

    Usage:
        client = MT5BridgeClient("http://192.168.1.10:8000")
        df = client.fetch_ohlc("XAUUSD", "1h", count=100)
        # df has columns: Datetime, Open, High, Low, Close
    """

    # Map QuantAgent timeframe strings → mt5-bridge timeframe strings
    TIMEFRAME_MAP = {
        "1m": "M1",
        "5m": "M5",
        "15m": "M15",
        "30m": "M30",
        "1h": "H1",
        "4h": "H4",
        "1d": "D1",
        "1w": "W1",
        "1mo": "MN1",
    }

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
        max_tick_age: Optional[timedelta] = None,
    ):
        """
        Initialize the MT5 Bridge client.

        Args:
            base_url: URL of the mt5-bridge server.
                      Falls back to env var MT5_BRIDGE_URL, then http://localhost:8000.
            timeout: HTTP request timeout in seconds.
            max_tick_age: Maximum accepted age for the latest tick before
                          treating the symbol as outside trading hours.
                          Falls back to env var MT5_TICK_MAX_AGE_SECONDS,
                          then 900 seconds.
        """
        if base_url is None:
            base_url = os.environ.get("MT5_BRIDGE_URL", "http://localhost:8000")
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.last_error: Optional[str] = None
        if max_tick_age is None:
            max_tick_age_seconds = int(os.environ.get("MT5_TICK_MAX_AGE_SECONDS", "900"))
            max_tick_age = timedelta(seconds=max_tick_age_seconds)
        self.max_tick_age = max_tick_age

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_health(self) -> dict:
        """Check if the mt5-bridge server is reachable and MT5 is connected."""
        try:
            resp = requests.get(f"{self.base_url}/health", timeout=5.0)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            return {"status": "error", "detail": str(e)}

    def get_tick(self, symbol: str) -> Optional[dict[str, Any]]:
        """Fetch the latest tick for a symbol from mt5-bridge."""
        try:
            resp = requests.get(f"{self.base_url}/tick/{symbol}", timeout=self.timeout)
            resp.raise_for_status()
            tick = resp.json()
            if isinstance(tick, dict):
                return tick
            print(f"Error fetching tick for {symbol}: unexpected response format")
            return None
        except requests.RequestException as e:
            print(f"Error fetching tick for {symbol}: {e}")
            return None

    def is_symbol_tradeable(self, symbol: str) -> tuple[bool, str]:
        """Check that a symbol has a fresh, usable tick before requesting OHLC."""
        tick = self.get_tick(symbol)
        if not tick:
            return False, f"tick not available for {symbol}"

        if not self._has_valid_tick_prices(tick):
            return False, f"symbol {symbol} has no valid bid/ask/last prices"

        tick_time = tick.get("time")
        if tick_time is None:
            return False, f"tick timestamp missing for {symbol}"

        try:
            tick_dt = datetime.fromtimestamp(int(tick_time), tz=timezone.utc)
        except (TypeError, ValueError, OSError):
            return False, f"invalid tick timestamp for {symbol}: {tick_time}"

        tick_age = datetime.now(timezone.utc) - tick_dt
        if tick_age > self.max_tick_age:
            return False, (
                f"symbol {symbol} appears outside trading hours "
                f"(latest tick age: {tick_age})"
            )

        return True, "ok"

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str = "1h",
        count: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch the most recent *count* OHLC bars from MT5.

        Args:
            symbol:    MT5 symbol (e.g. XAUUSD, EURUSD).
            timeframe: QuantAgent-style timeframe (1m, 5m, 1h, 4h, 1d …).
            count:     Number of bars to retrieve.

        Returns:
            pd.DataFrame with columns [Datetime, Open, High, Low, Close].
            Empty DataFrame on error.
        """
        self.last_error = None
        mt5_tf = self._resolve_timeframe(timeframe)
        if mt5_tf is None:
            self.last_error = f"unsupported timeframe '{timeframe}'"
            print(f"Error: {self.last_error}")
            return pd.DataFrame()

        tradeable, detail = self.is_symbol_tradeable(symbol)
        if not tradeable:
            self.last_error = detail
            print(f"Error fetching OHLC for {symbol}: {detail}")
            return pd.DataFrame()

        try:
            resp = requests.get(
                f"{self.base_url}/rates/{symbol}",
                params={"timeframe": mt5_tf, "count": count},
                timeout=self.timeout,
            )
            resp.raise_for_status()
            rates = resp.json()
            df = self._rates_to_dataframe(rates)
            if df.empty:
                self.last_error = f"mt5-bridge returned no OHLC data for {symbol} ({timeframe})"
            return df
        except requests.RequestException as e:
            self.last_error = str(e)
            print(f"Error fetching OHLC for {symbol}: {e}")
            return pd.DataFrame()

    def fetch_ohlc_range(
        self,
        symbol: str,
        timeframe: str,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> pd.DataFrame:
        """
        Fetch OHLC bars within a date range from MT5.

        Args:
            symbol:         MT5 symbol.
            timeframe:      QuantAgent-style timeframe.
            start_datetime: Start of the range (UTC-aware or naive-treated-as-UTC).
            end_datetime:   End of the range.

        Returns:
            pd.DataFrame with columns [Datetime, Open, High, Low, Close].
            Empty DataFrame on error.
        """
        self.last_error = None
        mt5_tf = self._resolve_timeframe(timeframe)
        if mt5_tf is None:
            self.last_error = f"unsupported timeframe '{timeframe}'"
            print(f"Error: {self.last_error}")
            return pd.DataFrame()

        tradeable, detail = self.is_symbol_tradeable(symbol)
        if not tradeable:
            self.last_error = detail
            print(f"Error fetching OHLC range for {symbol}: {detail}")
            return pd.DataFrame()

        # Convert to unix timestamps (mt5-bridge accepts int or ISO string)
        start_ts = self._to_unix(start_datetime)
        end_ts = self._to_unix(end_datetime)

        try:
            resp = requests.get(
                f"{self.base_url}/rates_range/{symbol}",
                params={
                    "timeframe": mt5_tf,
                    "start": start_ts,
                    "end": end_ts,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            rates = resp.json()
            df = self._rates_to_dataframe(rates)
            if df.empty:
                self.last_error = f"mt5-bridge returned no OHLC data for {symbol} ({timeframe})"
            return df
        except requests.RequestException as e:
            self.last_error = str(e)
            print(f"Error fetching OHLC range for {symbol}: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_timeframe(self, timeframe: str) -> Optional[str]:
        """Convert QuantAgent timeframe to mt5-bridge timeframe string."""
        return self.TIMEFRAME_MAP.get(timeframe.lower())

    @staticmethod
    def _has_valid_tick_prices(tick: dict[str, Any]) -> bool:
        """A tradeable symbol should expose at least one positive price field."""
        for field in ("bid", "ask", "last"):
            price = tick.get(field)
            if isinstance(price, (int, float)) and price > 0:
                return True
        return False

    @staticmethod
    def _to_unix(dt: datetime) -> int:
        """Convert a datetime to a unix timestamp (int seconds)."""
        if dt.tzinfo is None:
            # Treat naive datetimes as UTC
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    @staticmethod
    def _rates_to_dataframe(rates: list) -> pd.DataFrame:
        """
        Convert the JSON list from /rates or /rates_range into a DataFrame
        matching the format used by fetch_yfinance_data():

            columns = [Datetime, Open, High, Low, Close]

        The incoming data has keys: time, open, high, low, close,
        tick_volume, spread, real_volume.
        """
        if not rates:
            return pd.DataFrame()

        df = pd.DataFrame(rates)

        # Convert unix timestamps → datetime
        df["Datetime"] = pd.to_datetime(df["time"], unit="s", utc=True)
        # Strip timezone so it matches yfinance output (tz-naive)
        df["Datetime"] = df["Datetime"].dt.tz_localize(None)

        # Rename to match yfinance column casing
        df = df.rename(
            columns={
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
            }
        )

        # Keep only the columns that run_analysis() expects
        required = ["Datetime", "Open", "High", "Low", "Close"]
        df = df[required]

        return df
