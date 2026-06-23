# Phase 2A Implementation Complete - Testing Guide

## ✅ Changes Implemented

### 1. decision_agent.py
- ✅ Added import for PerformanceTracker
- ✅ Created `_get_learning_context()` function
- ✅ Modified `trade_decision_node()` to load and inject learning context
- ✅ Learning context is added before reports in the prompt
- ✅ Controlled by `USE_LEARNING` environment variable (default: true)

### 2. auto_trader.py
- ✅ Added import for PerformanceTracker
- ✅ Created `_record_to_performance_tracker()` method
- ✅ Modified `_close_tracked_trade()` to record to performance tracker
- ✅ Enhanced open_trades to store:
  - confidence_score
  - risk_reward_ratio
  - indicator_report
  - pattern_report
  - trend_report
  - entry_timing_reason
- ✅ Records full context when position closes

## 🧪 Testing Instructions

### Test 1: Verify Learning Context Loading
```bash
# Enable learning (default)
export USE_LEARNING=true

# Run single analysis
uv run auto_trader.py --once

# Check console output for:
# "✓ Learning context loaded for BTCUSD 30m"
# or
# "○ Insufficient data for learning context (BTCUSD 30m)"
```

### Test 2: Verify Performance Recording
```bash
# Run auto trader until a position closes
uv run auto_trader.py --once

# Check console output for:
# "✓ Trade recorded to performance tracker: WIN $XX.XX"

# Verify new trade in database
uv run performance_tracker.py report

# Should show updated trade count
```

### Test 3: Full Integration Test (Recommended)
```bash
# 1. Update config.json to focus on best setup
# Edit config.json:
# - Set min_confidence_score: 65
# - Enable only BTCUSD 30m
# - Disable other symbols/timeframes

# 2. Run once to generate a trade
uv run auto_trader.py --once

# 3. Wait for position to close (or manually close for testing)
# Then run again
uv run auto_trader.py --once

# 4. Analyze performance with new data
uv run scripts/analyze_performance.py --symbol BTCUSD --timeframe 30m

# 5. Check that learning insights improve
# Should see recommendations based on recent trades
```

### Test 4: Disable Learning (Fallback Test)
```bash
# Disable learning
export USE_LEARNING=false

# Run analysis
uv run auto_trader.py --once

# Should work normally without learning context
# Check console: no "Learning context loaded" message
```

## 📊 Expected Behavior

### With Learning Enabled (USE_LEARNING=true)

1. **First 10 trades**: No learning context
   - Console: "○ Insufficient data for learning context"
   - Decision agent uses base prompt only

2. **After 10+ trades**: Learning context injected
   - Console: "✓ Learning context loaded for {symbol} {timeframe}"
   - Decision prompt includes historical insights like:
     ```
     ## Historical Performance Context
     
     [PERFORMANCE] Performance Summary (Last 50 trades):
     - Win Rate: 53.8% (7W / 6L / 0BE)
     - Average Win: $43.59 | Average Loss: $-35.06
     
     [RECOMMENDATIONS] Actionable Recommendations:
     - Prefer entries when RSI is in 45-55 range
     - Avoid trades during London session (7.7% win rate)
     ```

3. **On position close**: Rich context recorded
   - Console: "✓ Trade recorded to performance tracker: WIN $XX.XX"
   - Database updated with full trade details

### With Learning Disabled (USE_LEARNING=false)

- Works exactly as before (backward compatible)
- No performance tracker integration
- No learning context in prompts

## 🔍 Verification Checklist

- [ ] `decision_agent.py` imports PerformanceTracker successfully
- [ ] Learning context loads after 10+ trades
- [ ] Learning context appears in decision prompt
- [ ] `auto_trader.py` records trades on close
- [ ] Recorded trades include confidence_score
- [ ] Recorded trades include agent reports
- [ ] Performance database grows with each closed trade
- [ ] Analysis reports show updated insights
- [ ] System works with USE_LEARNING=false

## 📝 Configuration Recommendations

Based on current data, update `config.json`:

```json
{
  "dry_run": false,
  "llm": {
    "provider": "openai",
    "agent_model": "gpt-4o-mini",
    "graph_model": "gpt-4o-mini",
    "temperature": 0.1
  },
  "risk": {
    "min_confidence_score": 65,  // Raised from 55
    "min_risk_reward_ratio": 1.5,  // Raised from 1.2
    "default_bars": 150
  },
  "symbols": [
    {
      "enabled": true,
      "provider": "mt5",
      "market_type": "forex",
      "symbol": "BTCUSD",
      "timeframe": "30m",  // Best performer: 53.8% win rate
      "bars": 150,
      "lot": 0.10
    },
    {
      "enabled": false,  // Disable poor performers
      "timeframe": "1h"  // Win rate: 8.3%
    },
    {
      "enabled": false,  // Disable poor performers
      "timeframe": "15m"  // Win rate: 0.0%
    }
  ]
}
```

## 🎯 Expected Improvements

After collecting 20+ more trades with learning enabled:

1. **Win Rate**: 27.6% → **45-55%**
   - System learns which conditions work
   - Avoids historically poor setups

2. **Confidence Filtering**: Better trade selection
   - Only trades with confidence ≥65
   - Focus on highest quality setups

3. **Time-based Optimization**: Focus NY session
   - NY session: 62.5% win rate
   - Avoid London: 7.7% win rate

4. **Pattern Recognition**: Learn what works
   - System identifies successful patterns
   - Weights decisions toward proven setups

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'performance_tracker'"
```bash
# Make sure you're in the project root
cd /path/to/QuantAgent
uv run auto_trader.py --once
```

### Learning context not loading
```bash
# Check if enough trades exist
uv run performance_tracker.py report BTCUSD 30m

# If less than 10 trades, need more data
# Run more trades or lower MIN_LEARNING_TRADES
export MIN_LEARNING_TRADES=5
```

### Trades not recording to performance tracker
```bash
# Check that trades are actually closing
# Look for "RESULT" events in CSV:
tail data/auto_trade_history.csv

# Verify performance_db.json is writable
ls -la data/performance_db.json
```

## 📚 Next Steps

1. ✅ Phase 2A Complete - Learning Integration
2. ⏭️ Phase 2B - Adaptive Confidence Threshold
3. ⏭️ Phase 2C - Entry Timing Optimizer
4. ⏭️ Phase 3 - Token Cost Optimization

Ready to start collecting better data! 🚀
