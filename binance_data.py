"""
Binance Data Client

HTTP client module for fetching OHLC data from Binance Spot Market.
Uses python-binance (https://github.com/sammchardy/python-binance).

No API key required — this uses public market data only.

Returns DataFrames in the same format as fetch_yfinance_data() so they can
be passed directly to WebTradingAnalyzer.run_analysis().
"""

from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from binance.client import Client
from binance.exceptions import BinanceAPIException


class BinanceAPIClient:
    """
    HTTP client for Binance public API.

    Usage:
        client = BinanceAPIClient()
        df = client.fetch_ohlc("BTCUSDT", "1h", count=100)
        # df has columns: Datetime, Open, High, Low, Close
    """

    # Map QuantAgent timeframe strings → Binance timeframe constants
    TIMEFRAME_MAP = {
        "1m": Client.KLINE_INTERVAL_1MINUTE,
        "5m": Client.KLINE_INTERVAL_5MINUTE,
        "15m": Client.KLINE_INTERVAL_15MINUTE,
        "30m": Client.KLINE_INTERVAL_30MINUTE,
        "1h": Client.KLINE_INTERVAL_1HOUR,
        "4h": Client.KLINE_INTERVAL_4HOUR,
        "1d": Client.KLINE_INTERVAL_1DAY,
        "1w": Client.KLINE_INTERVAL_1WEEK,
        "1mo": Client.KLINE_INTERVAL_1MONTH,
    }

    def __init__(self):
        """
        Initialize the Binance client without API keys (for public endpoints).
        """
        self.client = Client()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_status(self) -> dict:
        """Check Binance System Status API."""
        try:
            status = self.client.get_system_status()
            # return example: {'status': 0, 'msg': 'normal'}
            is_ok = status.get("status") == 0
            return {"status": "ok" if is_ok else "degraded", "detail": status}
        except Exception as e:
            return {"status": "error", "detail": str(e)}

    def fetch_ohlc(
        self,
        symbol: str,
        timeframe: str = "1h",
        count: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch the most recent *count* OHLC bars from Binance.

        Args:
            symbol:    Binance symbol (e.g. BTCUSDT, ETHUSDT).
            timeframe: QuantAgent-style timeframe (1m, 5m, 15m, 30m, 1h, 4h, 1d, 1w, 1mo).
            count:     Number of bars to retrieve. (Maximum 1000 per request on Binance)

        Returns:
            pd.DataFrame with columns [Datetime, Open, High, Low, Close].
            Empty DataFrame on error.
        """
        interval = self._resolve_timeframe(timeframe)
        if interval is None:
            print(f"Error: unsupported timeframe '{timeframe}' for Binance")
            return pd.DataFrame()

        try:
            # get_klines takes limit (max 1000)
            klines = self.client.get_klines(symbol=symbol, interval=interval, limit=count)
            return self._klines_to_dataframe(klines)
        except BinanceAPIException as e:
            print(f"Binance API error fetching OHLC for {symbol}: {e}")
            return pd.DataFrame()
        except Exception as e:
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
        Fetch OHLC bars within a date range from Binance.

        Args:
            symbol:         Binance symbol (e.g. BTCUSDT).
            timeframe:      QuantAgent-style timeframe.
            start_datetime: Start of the range.
            end_datetime:   End of the range.

        Returns:
            pd.DataFrame with columns [Datetime, Open, High, Low, Close].
            Empty DataFrame on error.
        """
        interval = self._resolve_timeframe(timeframe)
        if interval is None:
            print(f"Error: unsupported timeframe '{timeframe}' for Binance")
            return pd.DataFrame()

        start_str = str(self._to_unix_ms(start_datetime))
        end_str = str(self._to_unix_ms(end_datetime))

        try:
            klines = self.client.get_historical_klines(
                symbol=symbol, 
                interval=interval, 
                start_str=start_str, 
                end_str=end_str
            )
            return self._klines_to_dataframe(klines)
        except BinanceAPIException as e:
            print(f"Binance API error fetching OHLC range for {symbol}: {e}")
            return pd.DataFrame()
        except Exception as e:
            print(f"Error fetching OHLC range for {symbol}: {e}")
            return pd.DataFrame()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_timeframe(self, timeframe: str) -> Optional[str]:
        """Convert QuantAgent timeframe to Binance interval string."""
        return self.TIMEFRAME_MAP.get(timeframe.lower())

    @staticmethod
    def _to_unix_ms(dt: datetime) -> int:
        """Convert a datetime to a unix timestamp in milliseconds."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)

    @staticmethod
    def _klines_to_dataframe(klines: list) -> pd.DataFrame:
        """
        Convert Binance klines response to DataFrame matching
        the format used by fetch_yfinance_data():

            columns = [Datetime, Open, High, Low, Close]

        Binance Kline layout:
        [
            0: 1499040000000,      // Open time
            1: "0.01633322",       // Open
            2: "0.80000000",       // High
            3: "0.01575800",       // Low
            4: "0.01577100",       // Close
            ...
        ]
        """
        if not klines:
            return pd.DataFrame()

        df = pd.DataFrame(klines, columns=[
            "Datetime", "Open", "High", "Low", "Close", "Volume",
            "close_time", "qav", "num_trades", "taker_base_vol", "taker_quote_vol", "ignore"
        ])

        # Convert millisecond timestamps → datetime
        df["Datetime"] = pd.to_datetime(df["Datetime"], unit="ms", utc=True)
        
        # Strip timezone so it matches yfinance output (tz-naive)
        df["Datetime"] = df["Datetime"].dt.tz_localize(None)

        # Keep only the columns that run_analysis() expects
        required = ["Datetime", "Open", "High", "Low", "Close"]
        df = df[required]

        # Ensure numeric types
        for col in ["Open", "High", "Low", "Close"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        return df
