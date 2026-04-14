import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from auto_trader import AutoTradingEngine, MT5ExchangeAdapter, parse_risk_reward, timeframe_to_seconds


class AutoTraderTests(unittest.TestCase):
    def test_timeframe_to_seconds(self):
        self.assertEqual(timeframe_to_seconds("1m"), 60)
        self.assertEqual(timeframe_to_seconds("1h"), 3600)
        self.assertEqual(timeframe_to_seconds("4h"), 14400)

    def test_parse_risk_reward(self):
        self.assertEqual(parse_risk_reward("1:2.5"), 2.5)
        self.assertEqual(parse_risk_reward("2.1"), 2.1)

    def test_load_and_validate_config(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "dry_run": True,
                        "symbols": [
                            {
                                "enabled": True,
                                "provider": "binance",
                                "symbol": "BTCUSDT",
                                "timeframe": "1h"
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            engine = AutoTradingEngine(str(path))
            self.assertEqual(engine.validate_config(), [])

    def test_sync_open_trades_with_live_positions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "dry_run": True,
                        "symbols": [
                            {
                                "enabled": True,
                                "provider": "binance",
                                "market_type": "futures",
                                "symbol": "BTCUSDT",
                                "timeframe": "1h"
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            engine = AutoTradingEngine(str(path))
            item = {
                "provider": "binance",
                "market_type": "futures",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
            }

            engine._sync_open_trades_with_live_positions(
                item,
                [
                    {
                        "symbol": "BTCUSDT",
                        "side": "LONG",
                        "quantity": 0.25,
                        "entry_price": 101000.0,
                    }
                ],
            )

            tracked = engine.state["open_trades"]["binance:BTCUSDT:futures"]
            self.assertEqual(tracked["decision"], "LONG")
            self.assertEqual(tracked["quantity"], 0.25)
            self.assertEqual(tracked["entry_price"], 101000.0)

            engine._sync_open_trades_with_live_positions(item, [])
            self.assertNotIn("binance:BTCUSDT:futures", engine.state["open_trades"])

    def test_mt5_place_order_uses_bridge_schema(self):
        adapter = MT5ExchangeAdapter.__new__(MT5ExchangeAdapter)
        adapter.base_url = "http://127.0.0.1:8000"
        adapter.timeout = 5

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}

        with patch("auto_trader.requests.post", return_value=response) as mock_post:
            result = adapter.place_order(
                {
                    "symbol": "XAUUSD",
                    "lot": 0.01,
                    "comment": "test",
                    "magic": 123456,
                },
                "LONG",
                4765.6,
            )

        self.assertEqual(result["status"], "success")
        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["symbol"], "XAUUSD")
        self.assertEqual(payload["type"], "BUY")
        self.assertEqual(payload["volume"], 0.01)
        self.assertEqual(payload["comment"], "test")
        self.assertEqual(payload["magic"], 123456)
        self.assertNotIn("side", payload)


if __name__ == "__main__":
    unittest.main()
