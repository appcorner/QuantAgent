"""
Adaptive Confidence Threshold System

Dynamically adjusts minimum confidence threshold based on recent performance.
Goal: Trade more when winning, trade less (more selective) when losing.

Strategy:
- High win rate (>65%) + good R:R → Lower threshold (allow more trades)
- Medium win rate (55-65%) → Keep current threshold
- Low win rate (<55%) → Raise threshold (be more selective)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

try:
    from performance_tracker import PerformanceTracker
    TRACKER_AVAILABLE = True
except ImportError:
    TRACKER_AVAILABLE = False


class AdaptiveConfidence:
    """
    Dynamically adjust confidence threshold based on recent trading performance.
    """

    def __init__(
        self,
        default_threshold: float = 65.0,
        window_size: int = 50,
        min_trades_required: int = 10
    ):
        """
        Args:
            default_threshold: Fallback confidence threshold when insufficient data
            window_size: Number of recent trades to analyze
            min_trades_required: Minimum trades needed before adapting
        """
        self.default_threshold = default_threshold
        self.window_size = window_size
        self.min_trades_required = min_trades_required

    def calculate_threshold(
        self,
        symbol: str,
        timeframe: str,
        current_threshold: float | None = None
    ) -> dict[str, Any]:
        """
        Calculate adaptive confidence threshold based on recent performance.

        Returns:
            dict with:
            - threshold: Recommended confidence threshold
            - reason: Explanation for the threshold
            - win_rate: Recent win rate
            - avg_rr: Average risk/reward
            - sample_size: Number of trades analyzed
        """
        if not TRACKER_AVAILABLE:
            return {
                "threshold": self.default_threshold,
                "reason": "Performance tracker not available",
                "win_rate": 0.0,
                "avg_rr": 0.0,
                "sample_size": 0,
                "adapted": False
            }

        try:
            tracker = PerformanceTracker()
            recent_trades = tracker.get_recent_trades(
                symbol=symbol,
                timeframe=timeframe,
                limit=self.window_size
            )

            # Need minimum trades to adapt
            if len(recent_trades) < self.min_trades_required:
                return {
                    "threshold": self.default_threshold,
                    "reason": f"Insufficient data ({len(recent_trades)}/{self.min_trades_required} trades)",
                    "win_rate": 0.0,
                    "avg_rr": 0.0,
                    "sample_size": len(recent_trades),
                    "adapted": False
                }

            # Calculate performance metrics
            stats = tracker.calculate_win_rate(recent_trades)
            win_rate = stats["win_rate"]
            avg_rr = stats["avg_rr"]
            sample_size = stats["total"]

            # Current threshold (if provided)
            base_threshold = current_threshold if current_threshold else self.default_threshold

            # Adaptive logic
            new_threshold, reason = self._calculate_adaptive_threshold(
                win_rate=win_rate,
                avg_rr=avg_rr,
                base_threshold=base_threshold,
                sample_size=sample_size
            )

            return {
                "threshold": new_threshold,
                "reason": reason,
                "win_rate": win_rate,
                "avg_rr": avg_rr,
                "sample_size": sample_size,
                "adapted": new_threshold != base_threshold
            }

        except Exception as e:
            return {
                "threshold": self.default_threshold,
                "reason": f"Error calculating adaptive threshold: {e}",
                "win_rate": 0.0,
                "avg_rr": 0.0,
                "sample_size": 0,
                "adapted": False
            }

    def _calculate_adaptive_threshold(
        self,
        win_rate: float,
        avg_rr: float,
        base_threshold: float,
        sample_size: int
    ) -> tuple[float, str]:
        """
        Core adaptive logic for threshold calculation.

        Returns:
            (new_threshold, reason)
        """
        # Confidence bands based on sample size
        # Small sample = less aggressive adaptation
        confidence_factor = min(1.0, sample_size / 30.0)

        # Case 1: Excellent performance → Relax threshold (trade more)
        if win_rate > 0.65 and avg_rr > 1.5:
            adjustment = -10 * confidence_factor  # Lower by up to 10 points
            new_threshold = max(50.0, base_threshold + adjustment)
            return (
                new_threshold,
                f"Excellent performance ({win_rate*100:.1f}% win rate, {avg_rr:.2f} R:R) - lowering threshold to increase trade frequency"
            )

        # Case 2: Good performance → Slight relax
        if win_rate > 0.60 and avg_rr > 1.3:
            adjustment = -5 * confidence_factor
            new_threshold = max(55.0, base_threshold + adjustment)
            return (
                new_threshold,
                f"Good performance ({win_rate*100:.1f}% win rate, {avg_rr:.2f} R:R) - slightly lowering threshold"
            )

        # Case 3: Acceptable performance → Maintain
        if win_rate >= 0.55 and avg_rr >= 1.2:
            return (
                base_threshold,
                f"Acceptable performance ({win_rate*100:.1f}% win rate, {avg_rr:.2f} R:R) - maintaining threshold"
            )

        # Case 4: Below target → Increase threshold moderately
        if win_rate >= 0.45:
            adjustment = 5 * confidence_factor
            new_threshold = min(75.0, base_threshold + adjustment)
            return (
                new_threshold,
                f"Below target ({win_rate*100:.1f}% win rate) - raising threshold to be more selective"
            )

        # Case 5: Poor performance → Increase threshold significantly
        adjustment = 10 * confidence_factor
        new_threshold = min(80.0, base_threshold + adjustment)
        return (
            new_threshold,
            f"Poor performance ({win_rate*100:.1f}% win rate) - significantly raising threshold"
        )

    def get_threshold_for_config(
        self,
        config: dict[str, Any],
        symbol: str,
        timeframe: str
    ) -> float:
        """
        Get adaptive threshold for use in config.

        Args:
            config: Trading configuration dict
            symbol: Trading symbol
            timeframe: Chart timeframe

        Returns:
            Confidence threshold to use
        """
        # Check if adaptive confidence is enabled
        use_adaptive = config.get("risk", {}).get("use_adaptive_confidence", False)
        if not use_adaptive:
            return config.get("risk", {}).get("min_confidence_score", self.default_threshold)

        # Get current config threshold as base
        base_threshold = config.get("risk", {}).get("min_confidence_score", self.default_threshold)

        # Calculate adaptive threshold
        result = self.calculate_threshold(
            symbol=symbol,
            timeframe=timeframe,
            current_threshold=base_threshold
        )

        # Log adaptation
        if result["adapted"]:
            print(f"[ADAPTIVE] {symbol} {timeframe}: {base_threshold:.0f} → {result['threshold']:.0f}")
            print(f"           Reason: {result['reason']}")

        return result["threshold"]

    def get_status_report(self, symbols: list[tuple[str, str]]) -> str:
        """
        Generate status report for multiple symbol/timeframe combinations.

        Args:
            symbols: List of (symbol, timeframe) tuples

        Returns:
            Formatted status report
        """
        if not TRACKER_AVAILABLE:
            return "Adaptive confidence system unavailable (performance tracker not found)"

        lines = ["=" * 80]
        lines.append("ADAPTIVE CONFIDENCE STATUS REPORT")
        lines.append("=" * 80)

        for symbol, timeframe in symbols:
            result = self.calculate_threshold(symbol, timeframe)

            lines.append(f"\n{symbol} {timeframe}:")
            lines.append(f"  Threshold: {result['threshold']:.0f}")
            lines.append(f"  Win Rate: {result['win_rate']*100:.1f}% ({result['sample_size']} trades)")
            lines.append(f"  Avg R:R: {result['avg_rr']:.2f}")
            lines.append(f"  Status: {result['reason']}")

        lines.append("\n" + "=" * 80)
        return "\n".join(lines)


def main():
    """CLI interface for adaptive confidence."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python adaptive_confidence.py <command> [args]")
        print("\nCommands:")
        print("  calculate <symbol> <timeframe>  - Calculate adaptive threshold")
        print("  status <symbol1,tf1> <symbol2,tf2> ...  - Status report for multiple symbols")
        print("\nExample:")
        print("  python adaptive_confidence.py calculate BTCUSD 30m")
        print("  python adaptive_confidence.py status BTCUSD,30m XAUUSD,1h")
        return

    command = sys.argv[1]
    adapter = AdaptiveConfidence()

    if command == "calculate":
        if len(sys.argv) < 4:
            print("Error: calculate requires <symbol> <timeframe>")
            return

        symbol = sys.argv[2]
        timeframe = sys.argv[3]

        result = adapter.calculate_threshold(symbol, timeframe)

        print(f"\nAdaptive Confidence Threshold for {symbol} {timeframe}")
        print("=" * 60)
        print(f"Recommended Threshold: {result['threshold']:.0f}")
        print(f"Win Rate: {result['win_rate']*100:.1f}% ({result['sample_size']} trades)")
        print(f"Avg R:R: {result['avg_rr']:.2f}")
        print(f"Reason: {result['reason']}")
        print(f"Adapted: {'Yes' if result['adapted'] else 'No'}")

    elif command == "status":
        if len(sys.argv) < 3:
            print("Error: status requires at least one <symbol,timeframe> pair")
            return

        symbols = []
        for arg in sys.argv[2:]:
            parts = arg.split(",")
            if len(parts) == 2:
                symbols.append((parts[0], parts[1]))

        report = adapter.get_status_report(symbols)
        print(report)

    else:
        print(f"Unknown command: {command}")


if __name__ == "__main__":
    main()
