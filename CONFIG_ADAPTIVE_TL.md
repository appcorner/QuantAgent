# MT5 Adaptive Trailing Lock (ATL) Configuration Schema

This document describes the configuration options for the MT5 Adaptive Trailing Lock daemon (`mt5_adaptive_tl.py`).

## Adding to config.json

Add this section to your `config.json` to enable and configure the ATL daemon:

```json
{
  "adaptive_tl": {
    "enabled": false,
    "poll_interval_seconds": 5,
    "state_dir": "runtime/adaptive_tl",
      "below_born_be_keep_distance_enabled": true,
    "profit_stages": {
      "born_be": {
        "trigger_usd": 5,
        "lock_usd": 1,
        "description": "First profit milestone"
      },
      "pre_be": {
        "trigger_usd": 20,
        "lock_usd": 5,
        "description": "Building profit"
      },
      "be": {
        "trigger_usd": 50,
        "lock_usd": 30,
        "description": "Break-even zone"
      },
      "tl": {
        "trigger_usd": 70,
        "lock_usd": 50,
        "description": "Trailing zone"
      },
      "tp_trail": {
        "trigger_usd": 80,
        "lock_usd": 60,
        "remove_fixed_tp": true,
        "enable_high_track": true,
        "description": "TP trailing with high-track mode"
      }
    },
    "high_track_retrace_pct": 30
  }
}
```

## Configuration Reference

### `adaptive_tl` object
Main configuration block for the ATL daemon.

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `enabled` | boolean | `false` | Enable/disable ATL monitoring |
| `poll_interval_seconds` | integer | `5` | Seconds between position polls |
| `state_dir` | string | `"runtime/adaptive_tl"` | Directory for state files |
| `below_born_be_keep_distance_enabled` | boolean | `true` | In `below_born_be`, trail SL on new best profit while preserving price distance |
| `high_track_retrace_pct` | integer | `30` | Retrace % threshold to close position |

### `profit_stages` object
Defines the 5 profit-locking stages.

Each stage has:
- `trigger_usd`: Current profit USD needed to enter this stage
- `lock_usd`: Profit in USD to protect via SL adjustment
- `description` (optional): Human-readable stage name

#### Stage Progression

1. **below_born_be** (< $5)
   - Status: Monitor only
   - Action: No stage lock. Optional keep-distance SL trailing when `below_born_be_keep_distance_enabled = true`
   - Lock: 0 USD

2. **born_be** ($5 ≥ profit < $20)
   - Trigger: Profit reaches $5
   - Lock: $1 of profit
   - SL moved to protect $1 minimum

3. **pre_be** ($20 ≥ profit < $50)
   - Trigger: Profit reaches $20
   - Lock: $5 of profit
   - SL moved progressively

4. **be** ($50 ≥ profit < $70)
   - Trigger: Profit reaches $50
   - Lock: $30 of profit
   - Strong SL protection

5. **tl** ($70 ≥ profit < $80)
   - Trigger: Profit reaches $70
   - Lock: $50 of profit
   - Moving stop loss to trail

6. **tp_trail** ($80+)
   - Trigger: Profit reaches $80
   - Lock: $60 of profit
   - **High-Track Mode**: Enabled
   - Tracks peak profit; closes on 30% retrace

### `high_track_retrace_pct`
When high-track mode is active (TP Trail stage):
- Monitors best profit achieved
- Triggers close if profit drops by this percentage
- Default: 30% retrace closes position
- Example: If best profit = $100 USD, position closes if profit falls to $70 USD

## State Files

For each tracked symbol, two files are created in `state_dir`:

### `{SYMBOL}.json`
Persistent state for the position:
```json
{
  "ticket": 12345,
  "side": "BUY",
  "entry_price": 50000.00,
  "current_price": 51000.00,
  "current_profit_usd": 100.00,
  "best_profit_usd": 120.00,
  "best_price": 51200.00,
  "current_sl": 49980.00,
  "current_tp": 52000.00,
  "current_stage": "tp_trail",
  "stage_unlocked": true,
  "locked_profit_usd": 60.00,
  "dynamic_lock_follow": true,
  "high_track_active": true,
  "last_updated": "2026-04-24T10:30:45.123456",
  "opened_at": "2026-04-24T09:00:00.000000"
}
```

### `{SYMBOL}_events.jsonl`
Event log (one JSON object per line):
```jsonl
{"timestamp": "2026-04-24T10:15:00", "symbol": "EURUSD", "event_type": "position_reset", "details": {...}, "current_stage": "below_born_be", "best_profit_usd": 0.0}
{"timestamp": "2026-04-24T10:20:00", "symbol": "EURUSD", "event_type": "stage_unlocked", "details": {"stage": "born_be", "locked_profit_usd": 1.0}, "current_stage": "born_be", "best_profit_usd": 5.5}
{"timestamp": "2026-04-24T10:25:00", "symbol": "EURUSD", "event_type": "sl_modified", "details": {"old_sl": 49990.0, "new_sl": 49999.0, "reason": "Stage born_be lock"}, "current_stage": "born_be", "best_profit_usd": 5.5}
```

## Usage

### Running the Daemon

Monitor a single symbol:
```bash
python mt5_adaptive_tl.py --symbol EURUSD
```

Monitor multiple symbols:
```bash
python mt5_adaptive_tl.py --symbol EURUSD --symbol GBPUSD --symbol USDJPY
```

Single cycle (test mode):
```bash
python mt5_adaptive_tl.py --symbol EURUSD --once
```

Custom config and MT5 bridge:
```bash
python mt5_adaptive_tl.py --config custom_config.json --mt5-bridge http://192.168.1.100:5000 --symbol EURUSD --log-level DEBUG
```

### Running with auto_trader.py

The ATL daemon runs **separately** from `auto_trader.py`:

**Terminal 1: Entry Decisions**
```bash
python auto_trader.py --config config.json
```

**Terminal 2: Post-Entry Management**
```bash
python mt5_adaptive_tl.py --symbol EURUSD --symbol GBPUSD --log-level INFO
```

The daemon:
- Reads auto_trader state files (optional, monitors live MT5 positions directly)
- Modifies SL/TP via MT5 bridge
- Writes its own state and events
- Does NOT interfere with auto_trader decision logic

## Example Workflow

1. **10:00** - auto_trader enters LONG at $50,000 (EURUSD/USD)
   - Initial SL: $49,900
   - Initial TP: $51,000
   - Entry recorded in auto_trader state

2. **10:05** - ATL daemon starts tracking
   - Loads MT5 position
   - Current profit: $50 USD
   - Stage: `born_be` (profit >= $5)
   - Locks $1 of profit

3. **10:10** - Price rises to $50,100
   - Current profit: $100 USD → Stage: `pre_be`
   - Locks $5 → SL moved to $49,995
   - Event logged

4. **10:15** - Price rises to $50,300
   - Current profit: $300 USD → Stage: `tp_trail`
   - Locks $60 → SL moved to $50,240
   - High-track enabled

5. **10:20** - Price drops to $50,200 (best was $50,300)
   - Current profit: $200 USD
   - Retrace: 33% (exceeds 30% threshold)
   - Position auto-closed
   - Event: `position_closed_retrace`

## Troubleshooting

### State files not updating
- Check `state_dir` permissions
- Verify MT5 bridge is running and accessible
- Check logs: `python mt5_adaptive_tl.py --symbol EURUSD --log-level DEBUG`

### Position not being modified
- Ensure `adaptive_tl.enabled = true` in config (optional; daemon checks automatically)
- Verify `dry_run = false` in config if you want live modifications
- Check MT5 bridge `/modify` endpoint accepts the payload

### High-track closing too aggressively
- Reduce `high_track_retrace_pct` (e.g., 40% instead of 30%)
- Or adjust `tp_trail.trigger_usd` (e.g., 100 instead of 80)

### Daemon consuming too much CPU
- Increase `poll_interval_seconds` (e.g., 10 instead of 5)
- Trade-off: Lower response time to price changes

## Integration with auto_trader.py

The ATL daemon operates independently:
- ✅ Reads live positions from MT5 bridge (same source)
- ✅ Modifies SL/TP via MT5 bridge
- ❌ Does NOT call auto_trader functions
- ❌ Does NOT modify auto_trader state

This design allows:
- Running both daemons simultaneously
- Gradual adoption (test ATL before enabling in config)
- Easy rollback (stop daemon, SL/TP stays at last modified value)

## Future Enhancements

- [ ] Integrate into `auto_trader.py` as optional --follow-positions mode
- [ ] Support Binance Futures (modify via broker API)
- [ ] Adaptive retrace threshold based on market volatility
- [ ] Pyramid entry coordination with ATL stages
- [ ] Telegram/Discord notifications at each stage transition
