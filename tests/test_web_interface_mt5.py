import unittest

from mt5_data import MT5BridgeClient
from web_interface import _build_mt5_fetch_error


class WebInterfaceMT5Tests(unittest.TestCase):
    def test_build_mt5_fetch_error_uses_client_last_error(self):
        client = MT5BridgeClient(base_url="http://127.0.0.1:8000")
        client.last_error = "symbol XAUUSD appears outside trading hours (latest tick age: 8:00:00)"

        message = _build_mt5_fetch_error(client, "XAUUSD", "1h")

        self.assertEqual(
            message,
            "Cannot fetch MT5 data for XAUUSD (1h): symbol XAUUSD appears outside trading hours (latest tick age: 8:00:00).",
        )


if __name__ == "__main__":
    unittest.main()