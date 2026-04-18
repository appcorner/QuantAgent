from datetime import datetime, timedelta, timezone
import unittest
from unittest.mock import Mock, patch

import pandas as pd
import requests

from mt5_data import MT5BridgeClient


def _response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


class MT5BridgeClientTests(unittest.TestCase):
    def test_fetch_ohlc_uses_tick_precheck_before_rates(self):
        client = MT5BridgeClient(
            base_url="http://127.0.0.1:8000",
            max_tick_age=timedelta(minutes=15),
        )
        fresh_tick = {
            "time": int(datetime.now(timezone.utc).timestamp()),
            "time_msc": 0,
            "bid": 3300.0,
            "ask": 3300.5,
            "last": 3300.2,
            "volume": 1,
        }
        rates = [
            {
                "time": int(datetime.now(timezone.utc).timestamp()),
                "open": 3299.0,
                "high": 3301.0,
                "low": 3298.5,
                "close": 3300.0,
                "tick_volume": 10,
                "spread": 2,
                "real_volume": 0,
            }
        ]

        with patch("mt5_data.requests.get", side_effect=[_response(fresh_tick), _response(rates)]) as mock_get:
            df = client.fetch_ohlc("XAUUSD", "1h", count=1)

        self.assertFalse(df.empty)
        self.assertEqual(list(df.columns), ["Datetime", "Open", "High", "Low", "Close"])
        self.assertEqual(mock_get.call_args_list[0].args[0], "http://127.0.0.1:8000/tick/XAUUSD")
        self.assertEqual(mock_get.call_args_list[1].args[0], "http://127.0.0.1:8000/rates/XAUUSD")

    def test_fetch_ohlc_returns_empty_when_tick_is_stale(self):
        client = MT5BridgeClient(
            base_url="http://127.0.0.1:8000",
            max_tick_age=timedelta(minutes=15),
        )
        stale_tick = {
            "time": int((datetime.now(timezone.utc) - timedelta(hours=8)).timestamp()),
            "time_msc": 0,
            "bid": 3300.0,
            "ask": 3300.5,
            "last": 3300.2,
            "volume": 1,
        }

        with patch("mt5_data.requests.get", return_value=_response(stale_tick)) as mock_get:
            df = client.fetch_ohlc("XAUUSD", "1h", count=10)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)
        self.assertIn("outside trading hours", client.last_error)
        self.assertEqual(mock_get.call_count, 1)
        self.assertEqual(mock_get.call_args.args[0], "http://127.0.0.1:8000/tick/XAUUSD")

    def test_fetch_ohlc_range_returns_empty_when_tick_endpoint_fails(self):
        client = MT5BridgeClient(base_url="http://127.0.0.1:8000")
        start_dt = datetime(2026, 1, 1, tzinfo=timezone.utc)
        end_dt = datetime(2026, 1, 2, tzinfo=timezone.utc)

        with patch("mt5_data.requests.get", side_effect=requests.RequestException("boom")):
            df = client.fetch_ohlc_range("XAUUSD", "1h", start_dt, end_dt)

        self.assertIsInstance(df, pd.DataFrame)
        self.assertTrue(df.empty)
        self.assertEqual(client.last_error, "tick not available for XAUUSD")