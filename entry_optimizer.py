"""
Entry Timing Optimizer

Evaluates whether current price/market conditions are good for immediate entry,
even when the direction bias (LONG/SHORT) is clear.

Prevents:
- Chasing extended moves (price ran too far)
- Entering directly into resistance/support
- Trading inside messy consolidation
- Entry without proper confirmation

Goal: Improve entry quality → Better R:R and win rate
"""

from __future__ import annotations

import statistics
from typing import Any


class EntryOptimizer:
    """
    Optimize entry timing based on price action and market structure.
    """

    def __init__(
        self,
        max_extension_pct: float = 3.0,
        proximity_threshold_pct: float = 0.5,
        min_volume_ratio: float = 0.8
    ):
        """
        Args:
            max_extension_pct: Maximum % move from swing before considered extended
            proximity_threshold_pct: Distance % from S/R to consider "too close"
            min_volume_ratio: Minimum volume relative to average for confirmation
        """
        self.max_extension_pct = max_extension_pct
        self.proximity_threshold_pct = proximity_threshold_pct
        self.min_volume_ratio = min_volume_ratio

    def evaluate_entry_timing(
        self,
        decision: str,
        kline_data: dict[str, Any],
        indicator_report: str = "",
        pattern_report: str = ""
    ) -> dict[str, Any]:
        """
        Evaluate if now is a good time to enter the trade.

        Args:
            decision: "LONG" or "SHORT"
            kline_data: OHLCV data dict with keys: Open, High, Low, Close, Volume
            indicator_report: Technical indicator analysis (optional)
            pattern_report: Pattern analysis (optional)

        Returns:
            dict with:
            - should_enter_now: bool
            - reason: str (Thai explanation)
            - checks: dict of individual check results
        """
        if decision not in ("LONG", "SHORT"):
            return {
                "should_enter_now": False,
                "reason": "ทิศทางไม่ชัดเจน (ไม่ใช่ LONG หรือ SHORT)",
                "checks": {}
            }

        try:
            # Extract recent candles
            closes = kline_data.get("Close", [])
            highs = kline_data.get("High", [])
            lows = kline_data.get("Low", [])
            volumes = kline_data.get("Volume", [])

            if not closes or len(closes) < 20:
                return {
                    "should_enter_now": True,  # Default to allow if insufficient data
                    "reason": "ข้อมูลไม่เพียงพอสำหรับการประเมิน - อนุญาตเข้า",
                    "checks": {}
                }

            current_price = closes[-1]
            recent_candles = 10

            # Check 1: Price Extension
            extension_check = self._check_price_extension(
                decision, current_price, highs[-recent_candles:], lows[-recent_candles:]
            )

            # Check 2: Proximity to S/R
            sr_check = self._check_sr_proximity(
                decision, current_price, highs[-20:], lows[-20:]
            )

            # Check 3: Volume Confirmation
            volume_check = self._check_volume_confirmation(
                volumes[-10:] if len(volumes) >= 10 else volumes
            )

            # Check 4: Momentum Confirmation
            momentum_check = self._check_momentum_confirmation(
                closes[-5:] if len(closes) >= 5 else closes, decision
            )

            checks = {
                "extension": extension_check,
                "support_resistance": sr_check,
                "volume": volume_check,
                "momentum": momentum_check
            }

            # Decision logic
            blockers = [
                check for check in checks.values()
                if not check["passed"] and check.get("severity") == "high"
            ]

            warnings = [
                check for check in checks.values()
                if not check["passed"] and check.get("severity") == "medium"
            ]

            # High severity blocker → Don't enter
            if blockers:
                reasons = [check["reason"] for check in blockers]
                return {
                    "should_enter_now": False,
                    "reason": " | ".join(reasons),
                    "checks": checks
                }

            # Multiple warnings → Don't enter
            if len(warnings) >= 2:
                reasons = [check["reason"] for check in warnings]
                return {
                    "should_enter_now": False,
                    "reason": "คุณภาพ entry ต่ำ: " + " และ ".join(reasons),
                    "checks": checks
                }

            # Passed all checks or minor warnings only
            return {
                "should_enter_now": True,
                "reason": "Entry timing ดี - สามารถเข้าได้",
                "checks": checks
            }

        except Exception as e:
            return {
                "should_enter_now": True,  # Default to allow on error
                "reason": f"ไม่สามารถประเมิน entry timing ได้ ({str(e)}) - อนุญาตเข้า",
                "checks": {}
            }

    def _check_price_extension(
        self,
        decision: str,
        current_price: float,
        recent_highs: list[float],
        recent_lows: list[float]
    ) -> dict[str, Any]:
        """Check if price has extended too far from recent swing."""
        if decision == "LONG":
            swing_low = min(recent_lows) if recent_lows else current_price
            extension_pct = ((current_price - swing_low) / swing_low * 100) if swing_low > 0 else 0

            if extension_pct > self.max_extension_pct:
                return {
                    "passed": False,
                    "severity": "high",
                    "reason": f"ราคาวิ่งไปแล้ว {extension_pct:.1f}% จาก swing low - รอ pullback",
                    "value": extension_pct
                }
        else:  # SHORT
            swing_high = max(recent_highs) if recent_highs else current_price
            extension_pct = ((swing_high - current_price) / swing_high * 100) if swing_high > 0 else 0

            if extension_pct > self.max_extension_pct:
                return {
                    "passed": False,
                    "severity": "high",
                    "reason": f"ราคาวิ่งลงไปแล้ว {extension_pct:.1f}% จาก swing high - รอ retest",
                    "value": extension_pct
                }

        return {
            "passed": True,
            "severity": "none",
            "reason": "ราคายังไม่ extended",
            "value": extension_pct if 'extension_pct' in locals() else 0
        }

    def _check_sr_proximity(
        self,
        decision: str,
        current_price: float,
        recent_highs: list[float],
        recent_lows: list[float]
    ) -> dict[str, Any]:
        """Check if price is too close to major support/resistance."""
        if decision == "LONG":
            # Check proximity to recent resistance
            resistance = max(recent_highs) if recent_highs else current_price
            distance_pct = ((resistance - current_price) / current_price * 100) if current_price > 0 else 999

            if distance_pct < self.proximity_threshold_pct:
                return {
                    "passed": False,
                    "severity": "medium",
                    "reason": f"ใกล้แนวต้าน ({distance_pct:.2f}%) - อาจถูก reject",
                    "value": distance_pct
                }
        else:  # SHORT
            # Check proximity to recent support
            support = min(recent_lows) if recent_lows else current_price
            distance_pct = ((current_price - support) / current_price * 100) if current_price > 0 else 999

            if distance_pct < self.proximity_threshold_pct:
                return {
                    "passed": False,
                    "severity": "medium",
                    "reason": f"ใกล้แนวรับ ({distance_pct:.2f}%) - อาจเกิด bounce",
                    "value": distance_pct
                }

        return {
            "passed": True,
            "severity": "none",
            "reason": "ห่างจาก S/R เพียงพอ",
            "value": distance_pct if 'distance_pct' in locals() else 999
        }

    def _check_volume_confirmation(self, recent_volumes: list[float]) -> dict[str, Any]:
        """Check if volume supports the move."""
        if not recent_volumes or len(recent_volumes) < 3:
            return {
                "passed": True,  # Skip check if insufficient data
                "severity": "none",
                "reason": "ข้อมูล volume ไม่เพียงพอ",
                "value": 0
            }

        try:
            avg_volume = statistics.mean(recent_volumes[:-1])  # Exclude last candle
            current_volume = recent_volumes[-1]

            if avg_volume == 0:
                return {"passed": True, "severity": "none", "reason": "Volume ไม่มีข้อมูล", "value": 0}

            volume_ratio = current_volume / avg_volume

            if volume_ratio < self.min_volume_ratio:
                return {
                    "passed": False,
                    "severity": "medium",
                    "reason": f"Volume อ่อนแอ ({volume_ratio:.2f}x avg) - ขาด confirmation",
                    "value": volume_ratio
                }

            return {
                "passed": True,
                "severity": "none",
                "reason": f"Volume ดี ({volume_ratio:.2f}x avg)",
                "value": volume_ratio
            }

        except Exception:
            return {"passed": True, "severity": "none", "reason": "ไม่สามารถวิเคราะห์ volume", "value": 0}

    def _check_momentum_confirmation(self, recent_closes: list[float], decision: str) -> dict[str, Any]:
        """Check if momentum supports the direction."""
        if not recent_closes or len(recent_closes) < 3:
            return {
                "passed": True,
                "severity": "none",
                "reason": "ข้อมูลไม่เพียงพอสำหรับ momentum",
                "value": 0
            }

        try:
            # Calculate momentum (rate of change)
            old_price = recent_closes[0]
            current_price = recent_closes[-1]

            if old_price == 0:
                return {"passed": True, "severity": "none", "reason": "Momentum ไม่มีข้อมูล", "value": 0}

            momentum_pct = ((current_price - old_price) / old_price * 100)

            if decision == "LONG" and momentum_pct < -1.0:
                return {
                    "passed": False,
                    "severity": "medium",
                    "reason": f"Momentum ลงลึก ({momentum_pct:.1f}%) ขณะต้องการ LONG",
                    "value": momentum_pct
                }

            if decision == "SHORT" and momentum_pct > 1.0:
                return {
                    "passed": False,
                    "severity": "medium",
                    "reason": f"Momentum ขึ้นแรง ({momentum_pct:.1f}%) ขณะต้องการ SHORT",
                    "value": momentum_pct
                }

            return {
                "passed": True,
                "severity": "none",
                "reason": f"Momentum สอดคล้อง ({momentum_pct:.1f}%)",
                "value": momentum_pct
            }

        except Exception:
            return {"passed": True, "severity": "none", "reason": "ไม่สามารถวิเคราะห์ momentum", "value": 0}


def main():
    """CLI for testing entry optimizer."""
    import sys
    import json

    if len(sys.argv) < 2:
        print("Usage: python entry_optimizer.py <test_data_json>")
        print("\nExample test data:")
        print(json.dumps({
            "decision": "LONG",
            "kline_data": {
                "Close": [100, 101, 102, 103, 104, 105],
                "High": [101, 102, 103, 104, 105, 106],
                "Low": [99, 100, 101, 102, 103, 104],
                "Volume": [1000, 1100, 1200, 1300, 1400, 1500]
            }
        }, indent=2))
        return

    try:
        test_data = json.loads(sys.argv[1])
        optimizer = EntryOptimizer()
        result = optimizer.evaluate_entry_timing(
            decision=test_data["decision"],
            kline_data=test_data["kline_data"]
        )

        print(json.dumps(result, indent=2, ensure_ascii=False))

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
