"""
Bitkub Data Client

HTTP client module for fetching OHLC data from Bitkub Exchange
via the public /tradingview/history endpoint.

No API key required — this uses public market data only.

Returns DataFrames in the same format as fetch_yfinance_data() so they can
be passed directly to WebTradingAnalyzer.run_analysis().
"""

import time
from datetime import datetime, timezone
from typing import List, Optional

import pandas as pd
import requests


class BitkubClient:
    """
    HTTP client for Bitkub public API.

    Usage:
        client = BitkubClient()
        df = client.fetch_ohlc("BTC_THB", "1h", count=100)
        # df has columns: Datetime, Open, High, Low, Close
    """

    BASE_URL = "https://api.bitkub.com"

    # Map QuantAgent timeframe strings → Bitkub TradingView resolution
    TIMEFRAME_MAP = {
        "1m": "1",
        "5m": "5",
        "15m": "15",
        "1h": "60",
        "4h": "240",
        "1d": "1D",
    }

    # Seconds per candle — used to calculate `from` timestamp for count-based fetch
    _TIMEFRAME_SECONDS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "1h": 3600,
        "4h": 14400,
        "1d": 86400,
    }

    def __init__(self, timeout: float = 30.0):
        """
        Initialize the Bitkub client.

        Args:
            timeout: HTTP request timeout in seconds.
        """
        self.timeout = timeout

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_status(self) -> dict:
        """Check Bitkub API status."""
        try:
            resp = requests.get(
                f"{self.BASE_URL}/api/status", timeout=5.0
            )
            resp.raise_for_status()
            data = resp.json()
            # data is a list of status objects
            all_ok = all(
                item.get("status") == "ok"
                for item in data
                if isinstance(item, dict)
            )
            return {"status": "ok" if all_ok else "degraded", "detail": data}
        except requests.RequestException as e:
            return {"status": "error", "detail": str(e)}

    def get_symbols(self) -> List[dict]:
        """
        Get all available trading symbols from Bitkub.

        Returns:
            List of dicts with keys: symbol, name, base_asset, quote_asset, status
        """
        try:
            resp = requests.get(
                f"{self.BASE_URL}/api/v3/market/symbols", timeout=self.timeout
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("error") != 0:
                print(f"Bitkub API error: {data}")
                return []
            return data.get("result", [])
        except requests.RequestException as e:
            print(f"Error fetching Bitkub symbols: {e}")
            return []

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str = "1h",
        count: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch the most recent *count* OHLC bars from Bitkub.

        Args:
            symbol:    Bitkub symbol (e.g. BTC_THB, ETH_THB).
            timeframe: QuantAgent-style timeframe (1m, 5m, 15m, 1h, 4h, 1d).
            count:     Number of bars to retrieve.

        Returns:
            pd.DataFrame with columns [Datetime, Open, High, Low, Close].
            Empty DataFrame on error.
        """
        resolution = self._resolve_timeframe(timeframe)
        if resolution is None:
            print(f"Error: unsupported timeframe '{timeframe}' for Bitkub")
            return pd.DataFrame()

        # Calculate from/to timestamps
        now_ts = int(time.time())
        seconds_per_bar = self._TIMEFRAME_SECONDS.get(timeframe.lower(), 3600)
        # Add a small buffer (2 extra bars) to ensure we get enough data
        from_ts = now_ts - (count + 2) * seconds_per_bar
        to_ts = now_ts

        return self._fetch_tradingview_history(symbol, resolution, from_ts, to_ts)

    def fetch_ohlc_range(
        self,
        symbol: str,
        timeframe: str,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> pd.DataFrame:
        """
        Fetch OHLC bars within a date range from Bitkub.

        Args:
            symbol:         Bitkub symbol (e.g. BTC_THB).
            timeframe:      QuantAgent-style timeframe.
            start_datetime: Start of the range.
            end_datetime:   End of the range.

        Returns:
            pd.DataFrame with columns [Datetime, Open, High, Low, Close].
            Empty DataFrame on error.
        """
        resolution = self._resolve_timeframe(timeframe)
        if resolution is None:
            print(f"Error: unsupported timeframe '{timeframe}' for Bitkub")
            return pd.DataFrame()

        from_ts = self._to_unix(start_datetime)
        to_ts = self._to_unix(end_datetime)

        return self._fetch_tradingview_history(symbol, resolution, from_ts, to_ts)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_timeframe(self, timeframe: str) -> Optional[str]:
        """Convert QuantAgent timeframe to Bitkub TradingView resolution."""
        return self.TIMEFRAME_MAP.get(timeframe.lower())

    @staticmethod
    def _to_unix(dt: datetime) -> int:
        """Convert a datetime to a unix timestamp (int seconds)."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())

    def _fetch_tradingview_history(
        self, symbol: str, resolution: str, from_ts: int, to_ts: int
    ) -> pd.DataFrame:
        """
        Call GET /tradingview/history and convert to DataFrame.

        Response format:
            {"s":"ok", "t":[...], "o":[...], "h":[...], "l":[...], "c":[...], "v":[...]}
        """
        try:
            resp = requests.get(
                f"{self.BASE_URL}/tradingview/history",
                params={
                    "symbol": symbol,
                    "resolution": resolution,
                    "from": from_ts,
                    "to": to_ts,
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()

            if data.get("s") != "ok":
                print(f"Bitkub TradingView API returned status: {data.get('s')}")
                return pd.DataFrame()

            return self._tradingview_to_dataframe(data)

        except requests.RequestException as e:
            print(f"Error fetching Bitkub OHLC for {symbol}: {e}")
            return pd.DataFrame()

    @staticmethod
    def _tradingview_to_dataframe(data: dict) -> pd.DataFrame:
        """
        Convert TradingView history response to DataFrame matching
        the format used by fetch_yfinance_data():

            columns = [Datetime, Open, High, Low, Close]

        Input keys: t (timestamps), o (open), h (high), l (low), c (close), v (volume)
        """
        timestamps = data.get("t", [])
        if not timestamps:
            return pd.DataFrame()

        df = pd.DataFrame(
            {
                "Datetime": pd.to_datetime(timestamps, unit="s", utc=True),
                "Open": data.get("o", []),
                "High": data.get("h", []),
                "Low": data.get("l", []),
                "Close": data.get("c", []),
            }
        )

        # Strip timezone so it matches yfinance output (tz-naive)
        df["Datetime"] = df["Datetime"].dt.tz_localize(None)

        # Ensure numeric types
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
