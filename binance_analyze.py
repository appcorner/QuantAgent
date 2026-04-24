#!/usr/bin/env python3
"""
Binance Analyze — CLI command for trading analysis using OHLC data from Binance.

This script mirrors the behaviour of the /api/analyze web endpoint but fetches
data from Binance's public API (Spot Market) instead of Yahoo Finance.

Usage examples:
    # Fetch the latest 100 bars on H1
    python binance_analyze.py --symbol BTCUSDT --timeframe 1h --bars 100

    # Fetch by date range
    python binance_analyze.py --symbol ETHUSDT --timeframe 4h \\
        --start "2025-01-01" --end "2025-01-31"

    # Export results to JSON
    python binance_analyze.py --symbol BTCUSDT --timeframe 1d --bars 50 \\
        --output result.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so local imports work
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from binance_data import BinanceAPIClient  # noqa: E402


# ═══════════════════════════════════════════════════════════════════════════
# Pretty-print helpers
# ═══════════════════════════════════════════════════════════════════════════

BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
SEP = "─" * 60


def _section(title: str, body: str) -> None:
    """Print a formatted section."""
    print(f"\n{CYAN}{BOLD}{'═' * 60}")
    print(f"  {title}")
    print(f"{'═' * 60}{RESET}")
    if body:
        print(body)


def print_results(results: dict) -> None:
    """Print analysis results in a human-friendly format."""
    if not results.get("success"):
        print(f"\n{RED}❌ Error: {results.get('error', 'Unknown error')}{RESET}")
        return

    print(f"\n{GREEN}{BOLD}✅ Analysis Complete{RESET}")
    print(f"{SEP}")
    print(f"  Asset     : {results.get('asset_name', 'N/A')}")
    print(f"  Timeframe : {results.get('timeframe', 'N/A')}")
    print(f"  Bars used : {results.get('data_length', 'N/A')}")
    print(SEP)

    _section("📊 Technical Indicators", results.get("technical_indicators", ""))
    _section("🔍 Pattern Analysis", results.get("pattern_analysis", ""))
    _section("📈 Trend Analysis", results.get("trend_analysis", ""))

    # Final decision
    decision = results.get("final_decision", {})
    if isinstance(decision, dict):
        if "raw" in decision:
            _section("📋 Final Decision", decision["raw"])
        else:
            body_lines = [
                f"  Decision          : {decision.get('decision', 'N/A')}",
                f"  Risk/Reward Ratio : {decision.get('risk_reward_ratio', 'N/A')}",
                f"  Forecast Horizon  : {decision.get('forecast_horizon', 'N/A')}",
                f"  Justification     : {decision.get('justification', 'N/A')}",
                f"  Confidence Level  : {decision.get('confidence_level', 'N/A')}",
                f"  Confidence Score  : {decision.get('confidence_score', 'N/A')}",
                f"  Should Enter Now  : {decision.get('should_enter_now', 'N/A')}",
                f"  Entry Timing      : {decision.get('entry_timing_reason', 'N/A')}",
            ]
            _section("📋 Final Decision", "\n".join(body_lines))

    # Image file info
    print(f"\n{YELLOW}📁 Chart images saved:{RESET}")
    print(f"  • {results.get('pattern_image_filename', 'data/<symbol>/kline_chart.png')}")
    print(f"  • {results.get('trend_image_filename', 'data/<symbol>/trend_graph.png')}")


# ═══════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run QuantAgent trading analysis on OHLC data from Binance Exchange.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--symbol",
        required=True,
        help="Binance symbol, e.g. BTCUSDT, ETHUSDT, DOTUSDT",
    )
    parser.add_argument(
        "--timeframe",
        default="1h",
        choices=list(BinanceAPIClient.TIMEFRAME_MAP.keys()),
        help="Candle timeframe (default: 1h)",
    )
    parser.add_argument(
        "--bars",
        type=int,
        default=100,
        help="Number of most-recent bars to fetch (default: 100). Ignored if --start/--end are given.",
    )
    parser.add_argument(
        "--start",
        default=None,
        help="Start datetime for date-range mode (YYYY-MM-DD or 'YYYY-MM-DD HH:MM')",
    )
    parser.add_argument(
        "--end",
        default=None,
        help="End datetime for date-range mode (YYYY-MM-DD or 'YYYY-MM-DD HH:MM')",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Path to write JSON results (optional)",
    )
    return parser


def _parse_dt(value: str) -> datetime:
    """Parse a user-supplied datetime string."""
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(value, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse '{value}'. Use YYYY-MM-DD or 'YYYY-MM-DD HH:MM'."
    )


def main() -> None:
    args = build_parser().parse_args()

    # ── 1. Check Binance status ────────────────────────────────────────
    client = BinanceAPIClient()

    print(f"{CYAN}Checking Binance API status …{RESET}")
    status = client.check_status()
    if status.get("status") == "error":
        print(f"{RED}❌ Cannot reach Binance API: {status.get('detail')}{RESET}")
        sys.exit(1)
    print(f"{GREEN}✅ Binance API is {status.get('status', 'unknown')}{RESET}")

    # ── 2. Fetch OHLC data ────────────────────────────────────────────
    symbol = args.symbol.upper()
    timeframe = args.timeframe

    if args.start and args.end:
        start_dt = _parse_dt(args.start)
        end_dt = _parse_dt(args.end)
        print(f"Fetching {symbol} {timeframe} from {start_dt} to {end_dt} …")
        df = client.fetch_ohlc_range(symbol, timeframe, start_dt, end_dt)
    else:
        print(f"Fetching {symbol} {timeframe} latest {args.bars} bars …")
        df = client.fetch_ohlc(symbol, timeframe, count=args.bars)

    if df.empty:
        print(f"{RED}❌ No data returned for {symbol}{RESET}")
        sys.exit(1)

    print(f"{GREEN}✅ Received {len(df)} bars ({df['Datetime'].min()} → {df['Datetime'].max()}){RESET}")

    # ── 3. Run analysis (reuse WebTradingAnalyzer pipeline) ───────────
    from web_interface import WebTradingAnalyzer  # noqa: E402

    analyzer = WebTradingAnalyzer()
    print(f"\n{YELLOW}Running analysis …{RESET}")

    results = analyzer.run_analysis(df, symbol, timeframe, artifact_symbol=symbol)
    formatted = analyzer.extract_analysis_results(results)

    # ── 4. Display results ────────────────────────────────────────────
    print_results(formatted)

    # ── 5. Optional JSON export ───────────────────────────────────────
    if args.output:
        export = {k: v for k, v in formatted.items() if k not in ("pattern_chart", "trend_chart")}
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(export, f, indent=2, ensure_ascii=False, default=str)
        print(f"\n{GREEN}📄 Results saved to {args.output}{RESET}")


if __name__ == "__main__":
    main()
