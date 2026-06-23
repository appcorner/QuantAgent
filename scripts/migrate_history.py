"""
Migrate trade history from CSV to structured JSON database.

This script converts the existing auto_trade_history.csv into the new
performance tracking database format with enhanced metadata.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


def parse_csv_trade(row: dict) -> dict | None:
    """Convert CSV row to structured trade record."""
    try:
        # Skip if not a completed trade
        if row.get("outcome") not in ("WIN", "LOSS", "BREAKEVEN"):
            return None

        # Build structured trade record
        trade = {
            "timestamp": row.get("timestamp", ""),
            "symbol": row.get("symbol", ""),
            "timeframe": row.get("timeframe", ""),
            "provider": row.get("provider", ""),
            "market_type": row.get("market_type", ""),
            "decision": row.get("decision", ""),
            "action": row.get("action", ""),
            "status": row.get("status", ""),
            "entry_price": float(row.get("price", 0) or 0),
            "quantity": float(row.get("quantity", 0) or 0),
            "sl": float(row.get("sl", 0) or 0),
            "tp": float(row.get("tp", 0) or 0),
            "outcome": row.get("outcome", ""),
            "pnl": float(row.get("pnl", 0) or 0),
            "confidence_score": float(row.get("confidence_score", 0) or 0),
            "risk_reward_ratio": float(row.get("risk_reward_ratio", 0) or 0),
            "order_id": row.get("order_id", ""),
            "ticket": row.get("ticket", ""),
            "notes": row.get("notes", ""),
            "dry_run": row.get("dry_run", "False").lower() in ("true", "1"),
        }

        # Add market conditions if available
        atr = float(row.get("atr", 0) or 0)
        if atr > 0:
            trade["market_conditions"] = {
                "atr": atr
            }

        # Calculate actual R:R if we have PnL
        pnl = trade["pnl"]
        entry = trade["entry_price"]
        sl = trade["sl"]

        if entry > 0 and sl > 0 and pnl != 0:
            risk = abs(entry - sl)
            if risk > 0:
                reward = abs(pnl / trade["quantity"]) if trade["quantity"] > 0 else abs(pnl)
                trade["actual_rr"] = reward / risk

        # Add context placeholders
        trade["entry_reason"] = row.get("notes", "")
        trade["exit_reason"] = "Migrated from CSV - reason not available"

        return trade

    except Exception as e:
        print(f"Warning: Failed to parse row: {e}")
        return None


def migrate_csv_to_json(csv_path: str, json_path: str, dry_run: bool = False):
    """
    Migrate CSV trade history to JSON performance database.

    Args:
        csv_path: Path to auto_trade_history.csv
        json_path: Path to output performance_db.json
        dry_run: If True, only show what would be migrated without writing
    """
    csv_file = Path(csv_path)
    json_file = Path(json_path)

    if not csv_file.exists():
        print(f"Error: CSV file not found: {csv_path}")
        return

    # Read CSV
    print(f"Reading trades from: {csv_path}")
    trades = []
    skipped = 0

    with csv_file.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            trade = parse_csv_trade(row)
            if trade:
                trades.append(trade)
            else:
                skipped += 1

    print(f"\nMigration Summary:")
    print(f"  Total CSV rows read: {skipped + len(trades)}")
    print(f"  Completed trades found: {len(trades)}")
    print(f"  Rows skipped (incomplete/open): {skipped}")

    # Show sample
    if trades:
        print(f"\nSample trade record:")
        sample = trades[0]
        print(json.dumps(sample, indent=2))

        # Calculate basic stats
        wins = sum(1 for t in trades if t["outcome"] == "WIN")
        losses = sum(1 for t in trades if t["outcome"] == "LOSS")
        breakeven = sum(1 for t in trades if t["outcome"] == "BREAKEVEN")
        total_pnl = sum(t["pnl"] for t in trades)

        print(f"\nHistorical Performance:")
        print(f"  Wins: {wins}")
        print(f"  Losses: {losses}")
        print(f"  Breakeven: {breakeven}")
        print(f"  Win Rate: {wins / (wins + losses) * 100:.1f}%" if (wins + losses) > 0 else "  Win Rate: N/A")
        print(f"  Total PnL: ${total_pnl:.2f}")

    # Write JSON
    if not dry_run:
        json_file.parent.mkdir(parents=True, exist_ok=True)

        db_data = {
            "version": "1.0",
            "created_at": datetime.utcnow().isoformat() + "Z",
            "migrated_from": str(csv_file),
            "trades": trades,
            "metadata": {
                "total_trades": len(trades),
                "last_updated": datetime.utcnow().isoformat() + "Z",
                "migration_date": datetime.utcnow().isoformat() + "Z"
            }
        }

        json_file.write_text(json.dumps(db_data, indent=2), encoding="utf-8")
        print(f"\n[OK] Migration complete! Database saved to: {json_path}")
    else:
        print(f"\n[DRY-RUN] Dry run mode - no files were written")
        print(f"   To perform actual migration, run without --dry-run flag")


def main():
    parser = argparse.ArgumentParser(description="Migrate CSV trade history to JSON performance database")
    parser.add_argument(
        "--input",
        default="data/auto_trade_history.csv",
        help="Input CSV file path (default: data/auto_trade_history.csv)"
    )
    parser.add_argument(
        "--output",
        default="data/performance_db.json",
        help="Output JSON file path (default: data/performance_db.json)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be migrated without writing files"
    )

    args = parser.parse_args()

    migrate_csv_to_json(
        csv_path=args.input,
        json_path=args.output,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
