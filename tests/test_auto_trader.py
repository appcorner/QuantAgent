import json
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch

from auto_trader import AutoTradingEngine, BitkubExchangeAdapter, MT5ExchangeAdapter, calculate_auto_sl_tp, main, parse_risk_reward, timeframe_to_seconds


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

    def test_calculate_auto_sl_tp_long(self):
        df = {
            "High": [100.0, 102.0, 103.5, 104.0, 105.0],
            "Low": [99.0, 100.5, 101.5, 102.5, 103.0],
            "Close": [100.5, 101.8, 102.7, 103.2, 104.6],
        }
        sl, tp, atr = calculate_auto_sl_tp(
            "LONG",
            104.6,
            df,
            {},
            {
                "use_auto_sl_tp": True,
                "atr_period": 3,
                "sl_atr_multiplier": 1.5,
                "tp_atr_multiplier": 2.0,
                "default_risk_reward_ratio": 1.5,
                "min_stop_distance_pct": 0.001,
            },
        )

        self.assertGreater(atr, 0)
        self.assertLess(sl, 104.6)
        self.assertGreater(tp, 104.6)

    def test_sync_records_closed_trade_result_with_order_id(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "config.json"
            path.write_text(
                json.dumps(
                    {
                        "dry_run": False,
                        "history_file": str(Path(tmp_dir) / "history.csv"),
                        "state_file": str(Path(tmp_dir) / "state.json"),
                        "status_file": str(Path(tmp_dir) / "status.json"),
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
            trade_key = engine._trade_key(item)
            engine.state["open_trades"][trade_key] = {
                "provider": "binance",
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "market_type": "futures",
                "decision": "LONG",
                "entry_price": 100000.0,
                "quantity": 0.1,
                "order_id": 123456,
                "ticket": "pos-1",
                "opened_at": "2026-01-01T00:00:00+00:00",
            }

            class StubAdapter:
                def get_closed_trade_outcome(self, item, tracked_trade):
                    return {
                        "close_price": 101000.0,
                        "pnl": 100.0,
                        "outcome": "WIN",
                        "order_id": tracked_trade.get("order_id"),
                        "ticket": tracked_trade.get("ticket"),
                        "reason": "Closed from exchange history",
                    }

            engine._sync_open_trades_with_live_positions(item, [], adapter=StubAdapter(), clear_missing=True)

            self.assertNotIn(trade_key, engine.state["open_trades"])
            self.assertEqual(engine.state["summary"]["wins"], 1)

            history_text = Path(tmp_dir, "history.csv").read_text(encoding="utf-8")
            self.assertIn("RESULT", history_text)
            self.assertIn("WIN", history_text)
            self.assertIn("123456", history_text)
            self.assertIn("pos-1", history_text)

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
                    "sl": 4750.0,
                    "tp": 4785.0,
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
        self.assertEqual(payload["sl"], 4750.0)
        self.assertEqual(payload["tp"], 4785.0)
        self.assertEqual(payload["comment"], "test")
        self.assertEqual(payload["magic"], 123456)
        self.assertNotIn("side", payload)

    def test_mt5_place_order_preserves_symbol_case(self):
        adapter = MT5ExchangeAdapter.__new__(MT5ExchangeAdapter)
        adapter.base_url = "http://127.0.0.1:8000"
        adapter.timeout = 5

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"ok": True}

        with patch("auto_trader.requests.post", return_value=response) as mock_post:
            adapter.place_order(
                {
                    "symbol": "XAUUSD.s",
                    "lot": 0.01,
                },
                "LONG",
                4765.6,
            )

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["symbol"], "XAUUSD.s")

    def test_mt5_get_closed_trade_outcome_uses_history_deals(self):
        adapter = MT5ExchangeAdapter.__new__(MT5ExchangeAdapter)
        adapter.base_url = "http://127.0.0.1:8000"
        adapter.timeout = 5

        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = [
            {
                "ticket": 7001,
                "order": 8001,
                "position_id": 12345678,
                "time": 1710000000,
                "time_msc": 1710000000100,
                "price": 2500.0,
                "profit": 0.0,
                "commission": -1.0,
                "swap": 0.0,
                "fee": 0.0,
            },
            {
                "ticket": 7002,
                "order": 8002,
                "position_id": 12345678,
                "time": 1710003600,
                "time_msc": 1710003600200,
                "price": 2510.0,
                "profit": 12.5,
                "commission": -1.5,
                "swap": 0.0,
                "fee": -0.5,
            },
        ]

        with patch("auto_trader.requests.get", return_value=response) as mock_get:
            result = adapter.get_closed_trade_outcome(
                {"symbol": "XAUUSD"},
                {"ticket": 12345678, "entry_price": 2500.0, "order_id": 8001},
            )

        self.assertEqual(mock_get.call_args.kwargs["params"], {"position": 12345678})
        self.assertEqual(result["close_price"], 2510.0)
        self.assertEqual(result["pnl"], 10.5)
        self.assertEqual(result["outcome"], "WIN")
        self.assertEqual(result["order_id"], 8001)
        self.assertEqual(result["ticket"], 12345678)
        self.assertEqual(result["close_order_id"], 8002)
        self.assertEqual(result["close_ticket"], 7002)

    def test_bitkub_get_closed_trade_outcome_uses_order_history(self):
        adapter = BitkubExchangeAdapter.__new__(BitkubExchangeAdapter)

        adapter._signed_get = Mock(
            return_value={
                "error": 0,
                "result": [
                    {
                        "order_id": "buy-1",
                        "txn_id": "buy-txn",
                        "side": "buy",
                        "amount": "1000.00",
                        "rate": "100000.00",
                        "fee": "2.50",
                        "credit": "0.00",
                        "ts": 1710000000000,
                        "order_closed_at": 1710000000000,
                    },
                    {
                        "order_id": "sell-1",
                        "txn_id": "sell-txn-1",
                        "side": "sell",
                        "amount": "0.004",
                        "rate": "110000.00",
                        "fee": "1.00",
                        "credit": "0.00",
                        "ts": 1710003600000,
                        "order_closed_at": 1710003600000,
                    },
                    {
                        "order_id": "sell-2",
                        "txn_id": "sell-txn-2",
                        "side": "sell",
                        "amount": "0.006",
                        "rate": "120000.00",
                        "fee": "1.50",
                        "credit": "0.50",
                        "ts": 1710007200000,
                        "order_closed_at": 1710007200000,
                    },
                ],
            }
        )

        result = adapter.get_closed_trade_outcome(
            {"symbol": "BTC_THB"},
            {
                "entry_price": 100000.0,
                "quantity": 0.01,
                "order_id": "open-123",
                "ticket": "",
                "opened_at": "2024-03-09T15:59:59+00:00",
            },
        )

        self.assertEqual(adapter._signed_get.call_args.args[0], "/api/v3/market/my-order-history")
        self.assertEqual(adapter._signed_get.call_args.args[1]["sym"], "BTC_THB")
        self.assertEqual(result["close_order_id"], "sell-2")
        self.assertEqual(result["close_ticket"], "sell-txn-2")
        self.assertAlmostEqual(result["close_price"], 116000.0)
        self.assertAlmostEqual(result["pnl"], 158.0)
        self.assertEqual(result["outcome"], "WIN")

    def test_main_handles_ctrl_c_without_traceback(self):
        parser = Mock()
        parser.parse_args.return_value = Namespace(
            config="config.json",
            once=False,
            validate_config=False,
            show_status=False,
        )
        engine = Mock()
        engine.validate_config.return_value = []
        engine.run_forever.side_effect = KeyboardInterrupt

        with patch("auto_trader.build_parser", return_value=parser), patch(
            "auto_trader.AutoTradingEngine", return_value=engine
        ), patch("builtins.print") as mock_print:
            exit_code = main()

        self.assertEqual(exit_code, 130)
        mock_print.assert_any_call("Stopped by user.")


if __name__ == "__main__":
    unittest.main()
