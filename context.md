# QuantAgent Project Context

## 📌 Overview
**QuantAgent** is an AI-powered Multi-Exchange trading analysis system. It connects to various trading APIs to fetch OHLCV (candlestick) data, processes technical indicators, and feeds them into Large Language Models (LLMs like OpenAI, Claude, Qwen) to generate automated trading decisions (Long/Short), technical analysis, pattern recognition, and trend summaries.

## 📡 Supported Data Sources & Exchanges
The project has evolved into a modular, multi-source system.
1. **YFinance (`yfinance_data.py` / `yfinance_analyze.py`)**: The primary fallback for traditional stocks, forex, and crypto (using tickers like `BTC-USD`).
2. **MetaTrader 5 (`mt5_data.py` / `mt5_analyze.py`)**: Connects to brokers via an `mt5-bridge` server.
3. **Bitkub (`bitkub_data.py` / `bitkub_analyze.py`)**: Native integration with Bitkub's Public REST API for Thai crypto assets (e.g. `BTC_THB`).
4. **Binance (`binance_data.py` / `binance_analyze.py`)**: Native integration using the `python-binance` library (e.g. `BTCUSDT`).

## ⚙️ Core Architecture & Files
* **`web_interface.py`**: The Flask backend application. It serves the UI and exposes the REST API endpoints used to orchestrate data fetching and AI analysis.
* **`templates/demo_new.html`**: The unified frontend. It features a modern, responsive UI with:
  * Dynamic Data Source tabs.
  * Custom Asset management grids that dynamically filter based on the active source.
  * Logic that seamlessly swaps between analyzing a specific Date Range or the latest N Bars (Use Current Time).
* **`data/custom_assets.json`**: Persists user-defined favorite symbols. The data structure maps the symbol directly to the source (Format: `[{"symbol": "XAUUSD", "source": "mt5"}]`).
* **`trading_graph.py`**: Handles drawing technical and pattern charts via `matplotlib` and saves them locally for the frontend to render.

## 🔌 API Endpoints
* **Analysis Endpoints**: 
  * `/api/analyze` (YFinance)
  * `/api/analyze-mt5` (MT5)
  * `/api/analyze-bitkub` (Bitkub)
  * `/api/analyze-binance` (Binance)
* **Custom Asset Endpoints**: 
  * `/api/save-custom-asset`
  * `/api/delete-custom-asset`
  * `/api/custom-assets`

## 🛠️ Recent Fixes & Critical Logic (For AI Context)
1. **Datetime vs Bars Logic**: 
   The frontend allows the user to check **"Use Current Time (Fetch latest bars)"**. 
   * When checked: The backend (across all sources) ignores any start/end date and cleanly slices exactly the `N` number of requested bars backwards from the current time. 
   * When unchecked: The user inputs an explicit Start Date and End Date via a Native HTML calendar, and the backend routes this to the `fetch_ohlc_range()` methods.
2. **State Management**:
   The `demo_new.html` has had its Javascript highly optimized to remove duplicates. It relies purely on the server (`web_interface.py`) for maintaining the truth state of custom assets.

## 🤖 AI Trading Agents (MCP)
The system includes **Model Context Protocol (MCP)** servers allowing external AI Agents to execute trades autonomously:
* **`mcp_servers/mt5_trading_server.py`**: MT5 Trading (requires `mt5-bridge`).
* **`mcp_servers/binance_trading_server.py`**: Binance Spot & USDS-M Futures trading.
* **`mcp_servers/bitkub_trading_server.py`**: Bitkub Spot trading (HMAC-SHA256 authenticated).
These servers expose standard tools for checking balances, getting positions, placing, modifying, and closing orders.

## 🚀 How to Run
1. Install dependencies (e.g., `pip install python-binance pandas requests flask yfinance mcp ...`)
2. Configure `.env` tokens (OpenAI / Anthropic API keys, Exchanges API keys). Check `.env.sample`.
3. Launch the server: `python web_interface.py`
4. Access globally via `http://127.0.0.1:5000/demo`
