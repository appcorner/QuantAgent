# MT5 Adaptive Trailing Lock - Quick Start Guide

## What is ATL?

**Adaptive Trailing Lock (ATL)** is a daemon that automatically protects profits by progressively moving your Stop Loss upward as price moves in your favor.

Instead of a fixed SL/TP set at entry, ATL:
- Monitors your position's profit in real-time
- Unlocks profit-protection levels as you hit milestone profits
- Automatically closes on 30% drawdown from peak profit

## Installation

1. **Copy the files:**
   ```
   mt5_adaptive_tl.py       (Main daemon)
   CONFIG_ADAPTIVE_TL.md    (Full documentation)
   config_example_with_atl.json  (Example config)
   ```

2. **Add to your config.json** (copy from `config_example_with_atl.json`):
   ```json
   "adaptive_tl": {
     "enabled": false,
     "poll_interval_seconds": 5,
     "profit_stages": {
       "born_be": {"trigger_usd": 5, "lock_usd": 1},
       "pre_be": {"trigger_usd": 20, "lock_usd": 5},
       "be": {"trigger_usd": 50, "lock_usd": 30},
       "tl": {"trigger_usd": 70, "lock_usd": 50},
       "tp_trail": {"trigger_usd": 80, "lock_usd": 60}
     },
     "high_track_retrace_pct": 30
   }
   ```

## Usage

### Terminal 1: Entry Decisions (auto_trader.py)
```bash
python auto_trader.py --config config.json
```

### Terminal 2: Profit Protection (mt5_adaptive_tl.py)
```bash
python mt5_adaptive_tl.py --symbol EURUSD --symbol GBPUSD
```

## How It Works

### Example: EURUSD BUY @ 1.1000

| Time | Price | Profit | Stage | Action |
|------|-------|--------|-------|--------|
| 10:00 | 1.1000 | $0 | — | Entry SL=1.0990, TP=1.1100 |
| 10:05 | 1.1005 | $5 | **Born BE** | Lock $1 → Move SL to 1.0999 |
| 10:10 | 1.1020 | $20 | **Pre BE** | Lock $5 → Move SL to 1.1005 |
| 10:15 | 1.1050 | $50 | **BE** | Lock $30 → Move SL to 1.1030 |
| 10:20 | 1.1070 | $70 | **TL** | Lock $50 → Move SL to 1.1050 |
| 10:25 | 1.1080 | $80 | **TP Trail** | Lock $60 + Enable High-Track |
| 10:30 | 1.1076 | $76 | (Retrace) | 5% drop OK, continue |
| 10:35 | 1.1056 | $56 | (Retrace) | 30%+ drop → **AUTO CLOSE** |

### Stage Details

| Stage | Trigger | Lock | SL Moves | Mode |
|-------|---------|------|----------|------|
| Born BE | $5 profit | $1 | Slight | Initial protection |
| Pre BE | $20 profit | $5 | Gradual | Building confidence |
| BE | $50 profit | $30 | Strong | Break-even protection |
| TL | $70 profit | $50 | Aggressive | Trailing |
| TP Trail | $80 profit | $60 | Max + High-Track | 30% retrace closes |

## Key Settings

### `profit_stages.{stage}.trigger_usd`
- Profit (USD) needed to reach this stage
- Default: 5 → 20 → 50 → 70 → 80

### `profit_stages.{stage}.lock_usd`
- USD amount of profit to protect by moving SL
- Once you hit $80 profit, SL is protected by $60

### `high_track_retrace_pct`
- In TP Trail stage, auto-close if profit drops by this %
- Default: 30% (if best profit = $100, close at $70)

### `poll_interval_seconds`
- How often daemon checks position
- Lower = faster response, higher CPU
- Default: 5 seconds

## Test Mode

### Single cycle (no loop):
```bash
python mt5_adaptive_tl.py --symbol EURUSD --once
```

### Dry run (no modifications):
Ensure `dry_run: true` in config.json
```bash
python mt5_adaptive_tl.py --symbol EURUSD
# Prints [DRY RUN] modifications to console, doesn't modify MT5
```

### Enable modifications:
Set `dry_run: false` in config.json
```bash
python mt5_adaptive_tl.py --symbol EURUSD
# Actually modifies SL/TP in MT5
```

## Monitoring

### View current state:
```bash
cat runtime/adaptive_tl/EURUSD.json
```

### View event log:
```bash
tail -f runtime/adaptive_tl/EURUSD_events.jsonl
```

### State fields:
- `best_profit_usd`: Highest profit achieved
- `current_stage`: Which stage you're in
- `locked_profit_usd`: How much profit is protected
- `high_track_active`: Boolean, True when in TP Trail stage
- `dynamic_lock_follow`: SL is actively following high-water mark

## Troubleshooting

### Daemon not modifying SL/TP
- [ ] Check `dry_run: false` in config
- [ ] Verify MT5 bridge is running
- [ ] Check logs: `--log-level DEBUG`

### Closing too early on retrace
- Increase `high_track_retrace_pct` (e.g., 40 instead of 30)
- Or increase `tp_trail.trigger_usd` (e.g., 100 instead of 80)

### High CPU usage
- Increase `poll_interval_seconds` (e.g., 10 instead of 5)

### State not saving
- Check write permissions on `runtime/adaptive_tl/`
- Verify disk space

## Architecture

```
┌─────────────────────────────────────────┐
│        auto_trader.py                   │
│   (Entry decisions, 1h/4h/1d)           │
│   Trades: buy/sell at decision times    │
└──────────────┬──────────────────────────┘
               │ (records position to state)
               │
    ┌──────────▼──────────────┐
    │  MT5 Live Exchange      │
    │  (positions, balance)   │
    └──────────▲──────────────┘
               │ (polls continuously)
               │
┌──────────────┴──────────────┐
│  mt5_adaptive_tl.py         │
│  (Profit locking, 5-stage)  │
│  Modifies SL/TP + closes    │
└────────────────────────────┘
     (separate daemon)
```

- **Completely independent** processes
- **No interference** with entry logic
- **Easy to enable/disable** by starting/stopping daemon
- **Separate state** files (auto_trader vs. ATL)

## Configuration Template

```json
"adaptive_tl": {
  "enabled": false,
  "poll_interval_seconds": 5,
  "state_dir": "runtime/adaptive_tl",
  "profit_stages": {
    "born_be": {"trigger_usd": 5, "lock_usd": 1},
    "pre_be": {"trigger_usd": 20, "lock_usd": 5},
    "be": {"trigger_usd": 50, "lock_usd": 30},
    "tl": {"trigger_usd": 70, "lock_usd": 50},
    "tp_trail": {"trigger_usd": 80, "lock_usd": 60}
  },
  "high_track_retrace_pct": 30
}
```

## Tips

1. **Start with dry_run=true** to observe behavior
2. **Use --once flag** for testing: `python mt5_adaptive_tl.py --symbol EURUSD --once`
3. **Monitor state JSON** while running: `tail -f runtime/adaptive_tl/EURUSD.json`
4. **Check events log** for decision history: `tail -f runtime/adaptive_tl/EURUSD_events.jsonl`
5. **Adjust retrace %** based on market volatility
6. **Test with different poll intervals** to find the sweet spot

## Next Steps

- [ ] Copy `config_example_with_atl.json` values to your `config.json`
- [ ] Run auto_trader in one terminal
- [ ] Run `python mt5_adaptive_tl.py --symbol EURUSD --once` to test
- [ ] Monitor state files and adjust thresholds
- [ ] Enable `dry_run: false` when confident
- [ ] Start daemon: `python mt5_adaptive_tl.py --symbol EURUSD --symbol GBPUSD` (loop)

See [CONFIG_ADAPTIVE_TL.md](CONFIG_ADAPTIVE_TL.md) for complete reference.
