"""
Analyze trade performance and generate detailed reports.

This script provides comprehensive performance analytics including:
- Win rate and profitability analysis
- Pattern performance breakdown
- Market condition correlation analysis
- Time-based performance patterns
- Actionable recommendations for improvement
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from performance_tracker import PerformanceTracker


def print_section_header(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def analyze_performance(
    db_path: str = "data/performance_db.json",
    symbol: str | None = None,
    timeframe: str | None = None,
    limit: int = 100,
    generate_report: bool = True,
    save_metrics: bool = True
):
    """
    Run comprehensive performance analysis.

    Args:
        db_path: Path to performance database
        symbol: Filter by specific symbol (optional)
        timeframe: Filter by specific timeframe (optional)
        limit: Number of recent trades to analyze
        generate_report: Generate learning report
        save_metrics: Save metrics to file
    """
    tracker = PerformanceTracker(db_file=db_path)

    if not tracker.trades:
        print("[ERROR] No trades found in database.")
        print(f"   Database location: {db_path}")
        print(f"   Run migration first: python scripts/migrate_history.py")
        return

    # Filter description
    filter_desc = []
    if symbol:
        filter_desc.append(f"Symbol: {symbol}")
    if timeframe:
        filter_desc.append(f"Timeframe: {timeframe}")
    filter_text = " | ".join(filter_desc) if filter_desc else "All trades"

    print_section_header(f"Performance Analysis - {filter_text}")

    # Get filtered trades
    recent_trades = tracker.get_recent_trades(symbol=symbol, timeframe=timeframe, limit=limit)
    print(f"\n[ANALYSIS] Analyzing {len(recent_trades)} trades (from {len(tracker.trades)} total in database)")

    # Overall performance
    print_section_header("Overall Performance")
    overall = tracker.calculate_win_rate(recent_trades)

    print(f"\n{'Metric':<25} {'Value':<20}")
    print("-" * 45)
    print(f"{'Total Trades':<25} {overall['total']:<20}")
    print(f"{'Wins':<25} {overall['wins']:<20}")
    print(f"{'Losses':<25} {overall['losses']:<20}")
    print(f"{'Breakeven':<25} {overall['breakeven']:<20}")
    print(f"{'Win Rate':<25} {overall['win_rate']*100:.1f}%")
    print(f"{'Average Win':<25} ${overall['avg_win']:.2f}")
    print(f"{'Average Loss':<25} ${overall['avg_loss']:.2f}")
    print(f"{'Average R:R':<25} {overall['avg_rr']:.2f}")

    # Calculate expectancy
    if overall['total'] > 0:
        expectancy = (overall['win_rate'] * overall['avg_win']) + ((1 - overall['win_rate']) * overall['avg_loss'])
        print(f"{'Expected PnL/Trade':<25} ${expectancy:.2f}")

    # Pattern performance
    print_section_header("Pattern Performance")
    patterns = tracker.calculate_pattern_performance(min_occurrences=3)

    if patterns:
        print(f"\n{'Pattern':<30} {'Trades':<10} {'Win Rate':<12} {'Avg R:R':<10}")
        print("-" * 70)
        for pattern_name, stats in list(patterns.items())[:10]:
            print(
                f"{pattern_name:<30} "
                f"{stats['occurrences']:<10} "
                f"{stats['win_rate']*100:>6.1f}%     "
                f"{stats['avg_rr']:>6.2f}"
            )
    else:
        print("\n[WARNING] No pattern data available (requires pattern_report in trades)")

    # Market condition analysis
    print_section_header("Market Condition Performance")
    conditions = tracker.calculate_condition_performance()

    # RSI analysis
    if conditions.get("rsi_ranges"):
        print("\n[RSI] RSI Range Performance:")
        print(f"{'RSI Range':<20} {'Trades':<10} {'Win Rate':<12} {'Avg R:R':<10}")
        print("-" * 55)
        for rsi_range, stats in sorted(conditions["rsi_ranges"].items(), key=lambda x: x[1]["win_rate"], reverse=True):
            if stats["total"] > 0:
                print(
                    f"{rsi_range:<20} "
                    f"{stats['total']:<10} "
                    f"{stats['win_rate']*100:>6.1f}%     "
                    f"{stats['avg_rr']:>6.2f}"
                )

    # Confidence analysis
    if conditions.get("confidence_ranges"):
        print("\n[CONFIDENCE] Confidence Score Performance:")
        print(f"{'Confidence Range':<20} {'Trades':<10} {'Win Rate':<12} {'Avg R:R':<10}")
        print("-" * 55)
        for conf_range, stats in conditions["confidence_ranges"].items():
            if stats["total"] > 0:
                print(
                    f"{conf_range:<20} "
                    f"{stats['total']:<10} "
                    f"{stats['win_rate']*100:>6.1f}%     "
                    f"{stats['avg_rr']:>6.2f}"
                )

    # Volatility analysis
    if conditions.get("volatility_levels"):
        print("\n[VOLATILITY] Volatility (ATR) Performance:")
        print(f"{'Volatility Level':<20} {'Trades':<10} {'Win Rate':<12} {'Avg R:R':<10}")
        print("-" * 55)
        for vol_level, stats in conditions["volatility_levels"].items():
            if stats["total"] > 0:
                print(
                    f"{vol_level:<20} "
                    f"{stats['total']:<10} "
                    f"{stats['win_rate']*100:>6.1f}%     "
                    f"{stats['avg_rr']:>6.2f}"
                )

    # Time-based analysis
    if conditions.get("time_of_day"):
        print("\n[TIME] Time of Day Performance (UTC):")
        print(f"{'Time Session':<20} {'Trades':<10} {'Win Rate':<12} {'Avg R:R':<10}")
        print("-" * 55)
        for time_session, stats in conditions["time_of_day"].items():
            if stats["total"] > 0:
                print(
                    f"{time_session:<20} "
                    f"{stats['total']:<10} "
                    f"{stats['win_rate']*100:>6.1f}%     "
                    f"{stats['avg_rr']:>6.2f}"
                )

    # Learning report
    if generate_report:
        print_section_header("Learning Report for Decision Prompt")
        report = tracker.generate_learning_report(symbol=symbol, timeframe=timeframe, limit=limit)
        print("\n" + report)

    # Save metrics
    if save_metrics:
        print_section_header("Saving Metrics")
        metrics = tracker.save_metrics()
        print(f"\n[OK] Metrics saved to: {tracker.metrics_file}")

        # Show per-symbol summary
        if metrics["by_symbol"]:
            print("\n[SYMBOL] Performance by Symbol:")
            for sym, stats in sorted(metrics["by_symbol"].items(), key=lambda x: x[1]["total"], reverse=True):
                print(
                    f"  {sym:<10} "
                    f"Win Rate: {stats['win_rate']*100:>5.1f}%  "
                    f"Trades: {stats['total']:>3}  "
                    f"PnL: ${stats['avg_win'] * stats['wins'] + stats['avg_loss'] * stats['losses']:>7.2f}"
                )

        # Show per-timeframe summary
        if metrics["by_timeframe"]:
            print("\n[TIMEFRAME] Performance by Timeframe:")
            for tf, stats in sorted(metrics["by_timeframe"].items(), key=lambda x: x[1]["total"], reverse=True):
                print(
                    f"  {tf:<6} "
                    f"Win Rate: {stats['win_rate']*100:>5.1f}%  "
                    f"Trades: {stats['total']:>3}  "
                    f"Avg R:R: {stats['avg_rr']:>4.2f}"
                )

    # Summary and recommendations
    print_section_header("Key Insights & Recommendations")

    print("\n[INSIGHTS] Actionable Insights:")

    # Win rate assessment
    if overall["win_rate"] < 0.45:
        print("  [CRITICAL] Win rate is critically low (<45%) - immediate strategy revision needed")
        print("     -> Focus on higher confidence setups (70+ score)")
        print("     -> Reduce trade frequency, prioritize quality over quantity")
    elif overall["win_rate"] < 0.55:
        print("  [WARNING] Win rate is below target (<55%) - strategy needs improvement")
        print("     -> Review losing trades for common patterns")
        print("     -> Consider stricter entry criteria")
    elif overall["win_rate"] > 0.65:
        print("  [EXCELLENT] Excellent win rate (>65%) - current strategy is effective")
        print("     -> Consider slightly relaxing entry criteria to increase frequency")

    # R:R assessment
    if overall["avg_rr"] < 1.2:
        print("  [WARNING] Risk:Reward ratio is too low (<1.2)")
        print("     -> Adjust TP levels to capture more profit")
        print("     -> Consider tighter stop losses")
    elif overall["avg_rr"] > 1.8:
        print("  [GOOD] Strong Risk:Reward ratio (>1.8)")

    # Confidence insights
    if conditions.get("confidence_ranges"):
        high_conf = conditions["confidence_ranges"].get("very_high (80+)", {})
        low_conf = conditions["confidence_ranges"].get("low (50-60)", {})

        if high_conf.get("total", 0) >= 3:
            print(f"  [GOOD] High confidence trades (80+) show {high_conf['win_rate']*100:.0f}% win rate")
            print(f"     -> Prioritize these setups")

        if low_conf.get("total", 0) >= 3 and low_conf.get("win_rate", 0) < 0.45:
            print(f"  [WARNING] Low confidence trades (50-60) show only {low_conf['win_rate']*100:.0f}% win rate")
            print(f"     -> Consider raising minimum confidence threshold to 65+")

    print("\n")


def main():
    parser = argparse.ArgumentParser(description="Analyze trade performance and generate reports")
    parser.add_argument(
        "--db",
        default="data/performance_db.json",
        help="Path to performance database (default: data/performance_db.json)"
    )
    parser.add_argument(
        "--symbol",
        help="Filter by specific symbol (e.g., XAUUSD, BTCUSD)"
    )
    parser.add_argument(
        "--timeframe",
        help="Filter by specific timeframe (e.g., 15m, 30m, 1h)"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Number of recent trades to analyze (default: 100)"
    )
    parser.add_argument(
        "--no-report",
        action="store_true",
        help="Skip generating learning report"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Skip saving metrics to file"
    )

    args = parser.parse_args()

    analyze_performance(
        db_path=args.db,
        symbol=args.symbol,
        timeframe=args.timeframe,
        limit=args.limit,
        generate_report=not args.no_report,
        save_metrics=not args.no_save
    )


if __name__ == "__main__":
    main()
