import json
import sys
import types
import unittest
from unittest.mock import patch


dotenv_module = types.ModuleType("dotenv")
dotenv_module.load_dotenv = lambda *args, **kwargs: False


class _FastMCP:
    def __init__(self, *args, **kwargs):
        pass

    def tool(self):
        def decorator(func):
            return func

        return decorator

    def run(self, transport: str = "stdio"):
        return None


fastmcp_module = types.ModuleType("mcp.server.fastmcp")
fastmcp_module.FastMCP = _FastMCP

mcp_module = types.ModuleType("mcp")
server_module = types.ModuleType("mcp.server")

with patch.dict(
    sys.modules,
    {
        "dotenv": dotenv_module,
        "mcp": mcp_module,
        "mcp.server": server_module,
        "mcp.server.fastmcp": fastmcp_module,
    },
):
    from mcp_servers import mt5_trading_server


class MT5TradingServerTests(unittest.TestCase):
    def test_mt5_place_order_preserves_symbol_case(self):
        with patch.object(mt5_trading_server, "_post", return_value={"ok": True}) as mock_post:
            response = mt5_trading_server.mt5_place_order("XAUUSD.s", "buy", 0.01)

        payload = mock_post.call_args.args[1]
        self.assertEqual(payload["symbol"], "XAUUSD.s")
        self.assertEqual(payload["side"], "BUY")

        body = json.loads(response)
        self.assertEqual(body["status"], "success")

    def test_mt5_close_all_preserves_symbol_case_filter(self):
        with patch.object(mt5_trading_server, "_get", return_value=[]) as mock_get:
            response = mt5_trading_server.mt5_close_all("XAUUSD.s")

        mock_get.assert_called_once_with("/positions", params={"symbols": "XAUUSD.s"})
        body = json.loads(response)
        self.assertEqual(body["status"], "success")