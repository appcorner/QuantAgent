"""
Performance Tracker for QuantAgent Trading System

This module provides comprehensive tracking and analysis of trade performance,
enabling the system to learn from historical trades and improve decision quality.

Features:
- Structured trade history storage
- Pattern performance analysis
- Market condition correlation analysis
- Learning insights generation for decision prompts
- Win rate and profitability metrics by various dimensions
"""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


class PerformanceTracker:
    """
    Track and analyze trade performance to enable system learning.
    """

    def __init__(self, db_file: str = "data/performance_db.json", metrics_file: str = "data/performance_metrics.json"):
        self.db_file = Path(db_file)
        self.metrics_file = Path(metrics_file)
        self.db_file.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database if it doesn't exist
        if not self.db_file.exists():
            self._initialize_database()

        self.trades = self._load_database()

    def _initialize_database(self):
        """Initialize empty database structure."""
        initial_data = {
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "trades": [],
            "metadata": {
                "total_trades": 0,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        }
        self.db_file.write_text(json.dumps(initial_data, indent=2), encoding="utf-8")

    def _load_database(self) -> list[dict]:
        """Load trades from database."""
        try:
            data = json.loads(self.db_file.read_text(encoding="utf-8"))
            return data.get("trades", [])
        except Exception as e:
            print(f"Warning: Could not load database: {e}")
            return []

    def _save_database(self):
        """Save trades to database."""
        data = {
            "version": "1.0",
            "created_at": self.trades[0]["timestamp"] if self.trades else datetime.now(timezone.utc).isoformat(),
            "trades": self.trades,
            "metadata": {
                "total_trades": len(self.trades),
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
        }
        self.db_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def record_trade(self, trade_data: dict):
        """
        Record a complete trade with all relevant context.

        Expected fields in trade_data:
        - timestamp: ISO format timestamp
        - symbol: Trading symbol
        - timeframe: Chart timeframe
        - provider: Exchange/broker
        - decision: LONG/SHORT
        - entry_price: Entry price
        - exit_price: Exit price (when closed)
        - quantity: Position size
        - outcome: WIN/LOSS/BREAKEVEN
        - pnl: Profit/loss amount
        - confidence_score: Model confidence (0-100)
        - risk_reward_ratio: Intended R:R ratio
        - actual_rr: Actual R:R achieved

        Context fields (for learning):
        - indicator_report: Technical indicator signals
        - pattern_report: Chart patterns detected
        - trend_report: Trend analysis
        - market_conditions: Dict with RSI, MACD, ATR, etc.
        - entry_reason: Why trade was taken
        - exit_reason: Why trade was closed
        """
        # Enhance trade data with computed fields
        enhanced_trade = trade_data.copy()
        enhanced_trade["recorded_at"] = datetime.now(timezone.utc).isoformat()

        # Calculate actual risk-reward if not provided
        if "actual_rr" not in enhanced_trade and enhanced_trade.get("outcome") in ("WIN", "LOSS"):
            pnl = float(enhanced_trade.get("pnl", 0))
            entry = float(enhanced_trade.get("entry_price", 0))
            if entry > 0 and pnl != 0:
                risk_pct = abs(pnl / entry) if pnl < 0 else 0
                reward_pct = abs(pnl / entry) if pnl > 0 else 0
                if risk_pct > 0:
                    enhanced_trade["actual_rr"] = reward_pct / risk_pct

        self.trades.append(enhanced_trade)
        self._save_database()

    def get_recent_trades(self, symbol: str | None = None, timeframe: str | None = None, limit: int = 100) -> list[dict]:
        """
        Get recent trades, optionally filtered by symbol and timeframe.
        """
        filtered = self.trades

        if symbol:
            filtered = [t for t in filtered if t.get("symbol") == symbol]

        if timeframe:
            filtered = [t for t in filtered if t.get("timeframe") == timeframe]

        # Sort by timestamp descending and limit
        filtered = sorted(filtered, key=lambda t: t.get("timestamp", ""), reverse=True)
        return filtered[:limit]

    def calculate_win_rate(self, trades: list[dict] | None = None) -> dict:
        """
        Calculate win rate statistics.

        Returns:
            dict with wins, losses, breakeven, total, win_rate, avg_win, avg_loss
        """
        if trades is None:
            trades = self.trades

        if not trades:
            return {
                "wins": 0,
                "losses": 0,
                "breakeven": 0,
                "total": 0,
                "win_rate": 0.0,
                "avg_win": 0.0,
                "avg_loss": 0.0,
                "avg_rr": 0.0
            }

        completed = [t for t in trades if t.get("outcome") in ("WIN", "LOSS", "BREAKEVEN")]
        wins = [t for t in completed if t.get("outcome") == "WIN"]
        losses = [t for t in completed if t.get("outcome") == "LOSS"]
        breakeven = [t for t in completed if t.get("outcome") == "BREAKEVEN"]

        win_pnls = [float(t.get("pnl", 0)) for t in wins if t.get("pnl")]
        loss_pnls = [float(t.get("pnl", 0)) for t in losses if t.get("pnl")]

        # Calculate average R:R safely
        win_rrs = [float(t.get("actual_rr", 0)) for t in wins if t.get("actual_rr") and float(t.get("actual_rr", 0)) > 0]

        return {
            "wins": len(wins),
            "losses": len(losses),
            "breakeven": len(breakeven),
            "total": len(completed),
            "win_rate": len(wins) / len(completed) if completed else 0.0,
            "avg_win": statistics.mean(win_pnls) if win_pnls else 0.0,
            "avg_loss": statistics.mean(loss_pnls) if loss_pnls else 0.0,
            "avg_rr": statistics.mean(win_rrs) if win_rrs else 0.0
        }

    def calculate_pattern_performance(self, min_occurrences: int = 5) -> dict:
        """
        Analyze performance by detected patterns.

        Returns dict mapping pattern names to performance stats.
        """
        pattern_trades = defaultdict(list)

        for trade in self.trades:
            if trade.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
                continue

            pattern_report = trade.get("pattern_report", "")
            if not pattern_report:
                continue

            # Extract pattern names from report
            # Simple heuristic: look for common pattern names
            patterns = self._extract_patterns(pattern_report)
            for pattern in patterns:
                pattern_trades[pattern].append(trade)

        # Calculate stats for each pattern
        results = {}
        for pattern, trades in pattern_trades.items():
            if len(trades) >= min_occurrences:
                results[pattern] = self.calculate_win_rate(trades)
                results[pattern]["pattern"] = pattern
                results[pattern]["occurrences"] = len(trades)

        # Sort by win rate
        return dict(sorted(results.items(), key=lambda x: x[1]["win_rate"], reverse=True))

    def _extract_patterns(self, pattern_report: str) -> list[str]:
        """Extract pattern names from pattern report text."""
        patterns = []
        pattern_keywords = [
            "Double Bottom", "Double Top", "Head and Shoulders", "Inverse Head and Shoulders",
            "Triangle", "Ascending Triangle", "Descending Triangle", "Symmetrical Triangle",
            "Flag", "Pennant", "Wedge", "Channel", "Rectangle",
            "Cup and Handle", "Rounding Bottom", "Rounding Top",
            "Breakout", "Breakdown", "Support Bounce", "Resistance Rejection"
        ]

        report_lower = pattern_report.lower()
        for keyword in pattern_keywords:
            if keyword.lower() in report_lower:
                patterns.append(keyword)

        return patterns if patterns else ["Unknown Pattern"]

    def calculate_condition_performance(self) -> dict:
        """
        Analyze performance by market conditions.

        Returns dict with performance stats by:
        - RSI ranges
        - MACD signal strength
        - Volatility (ATR) levels
        - Time of day
        - Day of week
        """
        results = {
            "rsi_ranges": self._analyze_rsi_performance(),
            "macd_strength": self._analyze_macd_performance(),
            "volatility_levels": self._analyze_volatility_performance(),
            "time_of_day": self._analyze_time_performance(),
            "confidence_ranges": self._analyze_confidence_performance()
        }

        return results

    def _analyze_rsi_performance(self) -> dict:
        """Analyze performance by RSI ranges."""
        rsi_buckets = {
            "oversold (< 30)": [],
            "low (30-45)": [],
            "neutral (45-55)": [],
            "high (55-70)": [],
            "overbought (> 70)": []
        }

        for trade in self.trades:
            if trade.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
                continue

            conditions = trade.get("market_conditions", {})
            rsi = conditions.get("rsi")

            if rsi is None:
                continue

            rsi = float(rsi)
            if rsi < 30:
                rsi_buckets["oversold (< 30)"].append(trade)
            elif rsi < 45:
                rsi_buckets["low (30-45)"].append(trade)
            elif rsi < 55:
                rsi_buckets["neutral (45-55)"].append(trade)
            elif rsi < 70:
                rsi_buckets["high (55-70)"].append(trade)
            else:
                rsi_buckets["overbought (> 70)"].append(trade)

        return {k: self.calculate_win_rate(v) for k, v in rsi_buckets.items() if v}

    def _analyze_macd_performance(self) -> dict:
        """Analyze performance by MACD signal strength."""
        macd_buckets = {
            "strong_bullish": [],
            "weak_bullish": [],
            "neutral": [],
            "weak_bearish": [],
            "strong_bearish": []
        }

        for trade in self.trades:
            if trade.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
                continue

            conditions = trade.get("market_conditions", {})
            macd = conditions.get("macd")

            if macd is None:
                continue

            macd = float(macd)
            if macd > 5:
                macd_buckets["strong_bullish"].append(trade)
            elif macd > 1:
                macd_buckets["weak_bullish"].append(trade)
            elif macd > -1:
                macd_buckets["neutral"].append(trade)
            elif macd > -5:
                macd_buckets["weak_bearish"].append(trade)
            else:
                macd_buckets["strong_bearish"].append(trade)

        return {k: self.calculate_win_rate(v) for k, v in macd_buckets.items() if v}

    def _analyze_volatility_performance(self) -> dict:
        """Analyze performance by volatility (ATR) levels."""
        volatility_buckets = {
            "low": [],
            "medium": [],
            "high": []
        }

        atrs = [float(t.get("market_conditions", {}).get("atr", 0))
                for t in self.trades if t.get("market_conditions", {}).get("atr")]

        if not atrs:
            return {}

        low_threshold = statistics.quantiles(atrs, n=3)[0]
        high_threshold = statistics.quantiles(atrs, n=3)[1]

        for trade in self.trades:
            if trade.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
                continue

            conditions = trade.get("market_conditions", {})
            atr = conditions.get("atr")

            if atr is None:
                continue

            atr = float(atr)
            if atr < low_threshold:
                volatility_buckets["low"].append(trade)
            elif atr < high_threshold:
                volatility_buckets["medium"].append(trade)
            else:
                volatility_buckets["high"].append(trade)

        return {k: self.calculate_win_rate(v) for k, v in volatility_buckets.items() if v}

    def _analyze_time_performance(self) -> dict:
        """Analyze performance by time of day (UTC)."""
        time_buckets = {
            "asian (00-08)": [],
            "london (08-16)": [],
            "newyork (16-24)": []
        }

        for trade in self.trades:
            if trade.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
                continue

            timestamp = trade.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                hour = dt.hour

                if hour < 8:
                    time_buckets["asian (00-08)"].append(trade)
                elif hour < 16:
                    time_buckets["london (08-16)"].append(trade)
                else:
                    time_buckets["newyork (16-24)"].append(trade)
            except Exception:
                continue

        return {k: self.calculate_win_rate(v) for k, v in time_buckets.items() if v}

    def _analyze_confidence_performance(self) -> dict:
        """Analyze performance by confidence score ranges."""
        confidence_buckets = {
            "low (50-60)": [],
            "medium (60-70)": [],
            "high (70-80)": [],
            "very_high (80+)": []
        }

        for trade in self.trades:
            if trade.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
                continue

            confidence = trade.get("confidence_score")
            if confidence is None:
                continue

            confidence = float(confidence)
            if confidence < 60:
                confidence_buckets["low (50-60)"].append(trade)
            elif confidence < 70:
                confidence_buckets["medium (60-70)"].append(trade)
            elif confidence < 80:
                confidence_buckets["high (70-80)"].append(trade)
            else:
                confidence_buckets["very_high (80+)"].append(trade)

        return {k: self.calculate_win_rate(v) for k, v in confidence_buckets.items() if v}

    def generate_learning_report(self, symbol: str | None = None, timeframe: str | None = None, limit: int = 100) -> str:
        """
        Generate a learning report to inject into decision prompts.

        Returns a formatted string with actionable insights based on historical performance.
        """
        recent_trades = self.get_recent_trades(symbol=symbol, timeframe=timeframe, limit=limit)

        if len(recent_trades) < 10:
            return "Insufficient trade history for learning insights (minimum 10 trades required)."

        # Overall performance
        overall = self.calculate_win_rate(recent_trades)

        # Condition-based performance
        conditions = self.calculate_condition_performance()

        # Pattern performance
        patterns = self.calculate_pattern_performance()

        # Build report
        report_lines = []
        report_lines.append(f"[PERFORMANCE] Performance Summary (Last {len(recent_trades)} trades):")
        report_lines.append(f"- Win Rate: {overall['win_rate']*100:.1f}% ({overall['wins']}W / {overall['losses']}L / {overall['breakeven']}BE)")
        report_lines.append(f"- Average Win: ${overall['avg_win']:.2f} | Average Loss: ${overall['avg_loss']:.2f}")
        report_lines.append(f"- Average R:R Achieved: {overall['avg_rr']:.2f}")
        report_lines.append("")

        # RSI insights
        if conditions.get("rsi_ranges"):
            report_lines.append("[RSI] RSI Performance Insights:")
            for rsi_range, stats in sorted(conditions["rsi_ranges"].items(),
                                          key=lambda x: x[1]["win_rate"], reverse=True):
                if stats["total"] >= 3:
                    report_lines.append(
                        f"  - {rsi_range}: {stats['win_rate']*100:.0f}% win rate "
                        f"({stats['wins']}W/{stats['losses']}L)"
                    )
            report_lines.append("")

        # Confidence insights
        if conditions.get("confidence_ranges"):
            report_lines.append("[CONFIDENCE] Confidence Score Correlation:")
            for conf_range, stats in conditions["confidence_ranges"].items():
                if stats["total"] >= 3:
                    report_lines.append(
                        f"  - {conf_range}: {stats['win_rate']*100:.0f}% win rate "
                        f"({stats['total']} trades)"
                    )
            report_lines.append("")

        # Pattern insights
        if patterns:
            report_lines.append("[PATTERNS] Top Performing Patterns:")
            top_patterns = list(patterns.items())[:5]
            for pattern_name, stats in top_patterns:
                report_lines.append(
                    f"  - {pattern_name}: {stats['win_rate']*100:.0f}% win rate "
                    f"(R:R {stats['avg_rr']:.2f}, {stats['occurrences']} occurrences)"
                )
            report_lines.append("")

        # Actionable recommendations
        report_lines.append("[RECOMMENDATIONS] Actionable Recommendations:")

        # RSI recommendations
        if conditions.get("rsi_ranges"):
            best_rsi = max(conditions["rsi_ranges"].items(), key=lambda x: x[1]["win_rate"])
            worst_rsi = min(conditions["rsi_ranges"].items(), key=lambda x: x[1]["win_rate"])
            if best_rsi[1]["total"] >= 3 and worst_rsi[1]["total"] >= 3:
                report_lines.append(
                    f"  [GOOD] Prefer entries in {best_rsi[0]} range (win rate: {best_rsi[1]['win_rate']*100:.0f}%)"
                )
                report_lines.append(
                    f"  [AVOID] Avoid entries in {worst_rsi[0]} range (win rate: {worst_rsi[1]['win_rate']*100:.0f}%)"
                )

        # Confidence recommendations
        if conditions.get("confidence_ranges"):
            high_conf = conditions["confidence_ranges"].get("very_high (80+)", {})
            if high_conf.get("total", 0) >= 3:
                report_lines.append(
                    f"  [GOOD] High confidence (80+) trades show {high_conf['win_rate']*100:.0f}% win rate"
                )

        # Overall recommendation
        if overall["win_rate"] < 0.50:
            report_lines.append("  [WARNING] Overall win rate is below 50% - be more selective with entries")
        elif overall["win_rate"] > 0.65:
            report_lines.append("  [GOOD] Strong performance - current strategy is working well")

        return "\n".join(report_lines)

    def save_metrics(self):
        """Save aggregated metrics to metrics file."""
        metrics = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "overall": self.calculate_win_rate(),
            "by_symbol": {},
            "by_timeframe": {},
            "patterns": self.calculate_pattern_performance(),
            "conditions": self.calculate_condition_performance()
        }

        # Group by symbol
        symbols = set(t.get("symbol") for t in self.trades if t.get("symbol"))
        for symbol in symbols:
            symbol_trades = [t for t in self.trades if t.get("symbol") == symbol]
            metrics["by_symbol"][symbol] = self.calculate_win_rate(symbol_trades)

        # Group by timeframe
        timeframes = set(t.get("timeframe") for t in self.trades if t.get("timeframe"))
        for tf in timeframes:
            tf_trades = [t for t in self.trades if t.get("timeframe") == tf]
            metrics["by_timeframe"][tf] = self.calculate_win_rate(tf_trades)

        self.metrics_file.write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        return metrics


def main():
    """CLI interface for performance tracker."""
    import sys

    tracker = PerformanceTracker()

    if len(sys.argv) > 1 and sys.argv[1] == "report":
        symbol = sys.argv[2] if len(sys.argv) > 2 else None
        timeframe = sys.argv[3] if len(sys.argv) > 3 else None

        report = tracker.generate_learning_report(symbol=symbol, timeframe=timeframe)
        print(report)

        print("\n" + "="*60)
        print("Saving detailed metrics...")
        metrics = tracker.save_metrics()
        print(f"Metrics saved to: {tracker.metrics_file}")
        print(f"Total trades analyzed: {len(tracker.trades)}")
    else:
        print("Usage: python performance_tracker.py report [symbol] [timeframe]")
        print(f"Current database: {tracker.db_file}")
        print(f"Total trades: {len(tracker.trades)}")


if __name__ == "__main__":
    main()
