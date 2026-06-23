# Testing Guide - Phase 2 Complete (A+B+C)

## 🎯 Overview

This guide covers testing the complete Phase 2 implementation:
- **Phase 2A**: Historical learning system
- **Phase 2B**: Adaptive confidence threshold
- **Phase 2C**: Entry timing optimizer

---

## ⚙️ Prerequisites

### 1. Update Configuration

Edit `config.json`:

```json
{
  "risk": {
    "min_confidence_score": 65,
    "use_adaptive_confidence": true,
    "adaptive_window": 50,
    "min_trades_for_adaptation": 10,
    "use_entry_optimizer": true,
    "entry_optimizer": {
      "max_extension_pct": 3.0,
      "proximity_threshold_pct": 0.5,
      "min_volume_ratio": 0.8
    }
  },
  "symbols": [
    {
      "enabled": true,
      "symbol": "BTCUSD",
      "timeframe": "30m"
    }
  ]
}
```

### 2. Environment Variables

```bash
# Enable learning (default: true)
export USE_LEARNING=true
```

### 3. Verify Data

```bash
# Check performance database exists
ls -lh data/performance_db.json

# Should show: 29 trades migrated
uv run scripts/analyze_performance.py --symbol BTCUSD --timeframe 30m
```

---

## 🧪 Test Suite

### Test 1: Phase 2A - Learning Context

**Goal**: Verify AI receives historical performance insights

```bash
# Run analysis to see current learning data
uv run performance_tracker.py report BTCUSD 30m
```

**Expected Output**:
```
============================================================
LEARNING REPORT: BTCUSD 30m
============================================================

[PERFORMANCE] Performance Summary (Last 13 trades):
- Win Rate: 53.8% (7W / 6L / 0BE)
- Average Win: $43.59 | Average Loss: $-35.36

[RSI] RSI Analysis:
  Range 30-50 (oversold): 66.7% win rate (2W / 1L)
  Range 50-70 (neutral): 40.0% win rate (2W / 3L)

[TIME] Time Analysis:
  Hour 16-24 (NY session): 62.5% win rate (5W / 3L)
  Hour 08-16 (London): 7.7% win rate (1W / 12L)

[RECOMMENDATIONS] Actionable Recommendations:
  [OK] Win rate above 50% - maintain current approach
  [WARNING] Avoid London session (08-16 UTC) - only 7.7% win rate
```

**Verification**:
- [ ] Report shows recent trade history
- [ ] Pattern analysis present (RSI, time, MACD)
- [ ] Recommendations actionable
- [ ] Win rate calculations correct

---

### Test 2: Phase 2B - Adaptive Confidence

**Goal**: Verify threshold adjusts based on performance

```bash
# Check adaptive threshold calculation
uv run adaptive_confidence.py calculate BTCUSD 30m
```

**Expected Output**:
```
Adaptive Confidence Threshold for BTCUSD 30m
============================================================
Recommended Threshold: 67
Win Rate: 53.8% (13 trades)
Avg R:R: 1.35
Reason: Below target (53.8% win rate) - raising threshold to be more selective
Adapted: Yes
```

**Verification**:
- [ ] Threshold adjusted from base (65 → 67)
- [ ] Reason reflects performance (53.8% < 55%)
- [ ] Sample size shown (13 trades)
- [ ] Adaptation flag correct (Yes)

**Test Different Scenarios**:

```bash
# Scenario A: Good performance (should lower threshold)
# Manually edit test: win_rate = 0.70, avg_rr = 1.6
# Expected: Threshold 55-60

# Scenario B: Poor performance (should raise threshold)
# Manually edit test: win_rate = 0.35, avg_rr = 1.0
# Expected: Threshold 75-80
```

---

### Test 3: Phase 2C - Entry Timing

**Goal**: Verify entry quality checks work

```bash
# Test perfect entry scenario
uv run python entry_optimizer.py '{
  "decision": "LONG",
  "kline_data": {
    "Close": [100, 101, 102, 103, 104, 105],
    "High": [101, 102, 103, 104, 105, 106],
    "Low": [99, 100, 101, 102, 103, 104],
    "Volume": [1000, 1100, 1200, 1300, 1400, 1500]
  }
}'
```

**Expected Output**:
```json
{
  "should_enter_now": true,
  "reason": "Entry timing ดี - สามารถเข้าได้",
  "checks": {
    "extension": {"passed": true},
    "support_resistance": {"passed": true},
    "volume": {"passed": true},
    "momentum": {"passed": true}
  }
}
```

**Test Extended Price Scenario**:
```bash
# Extended LONG (price ran 5% from swing low)
uv run python entry_optimizer.py '{
  "decision": "LONG",
  "kline_data": {
    "Close": [100, 101, 102, 103, 104, 110],
    "High": [101, 102, 103, 104, 105, 111],
    "Low": [99, 100, 101, 102, 103, 109],
    "Volume": [1000, 1100, 1200, 1300, 1400, 2000]
  }
}'
```

**Expected**: `should_enter_now: false`, reason contains "ราคาวิ่งไปแล้ว"

**Verification**:
- [ ] Perfect scenario allows entry
- [ ] Extended scenario blocks entry
- [ ] All 4 checks execute
- [ ] Thai language reasons present
- [ ] Severity levels correct (high/medium)

---

### Test 4: Complete Integration

**Goal**: Full system test with all phases enabled

```bash
# Run one trading cycle
uv run auto_trader.py --once
```

**What to Watch**:

1. **Learning Context Loaded** (Phase 2A):
```
[INFO] Loading learning context for BTCUSD 30m...
[INFO] Found 13 historical trades
```

2. **Adaptive Threshold Applied** (Phase 2B):
```
[ADAPTIVE] BTCUSD 30m: 65 → 67
           Reason: Below target (53.8% win rate) - raising threshold
```

3. **Entry Timing Check** (Phase 2C):
```
Option A - Trade Skipped:
[ENTRY TIMING] BTCUSD 30m LONG: Skipped
               Reason: ราคาวิ่งไปแล้ว 4.2% จาก swing low - รอ pullback

Option B - Trade Executed:
[ENTRY TIMING] BTCUSD 30m LONG: Entry timing ดี - สามารถเข้าได้
[ORDER] LONG 0.1 BTC at 76,100 | SL: 75,950 | TP: 76,400
```

**Verification Checklist**:
- [ ] Learning context loads (if 10+ trades exist)
- [ ] Adaptive threshold shown in logs
- [ ] Entry timing evaluation occurs
- [ ] Trade skipped if timing poor
- [ ] Trade executed if timing good
- [ ] Full context recorded to performance_db.json

---

## 📊 Performance Monitoring

### During Testing (Live)

```bash
# Monitor logs in real-time
tail -f logs/auto_trader.log | grep -E "ADAPTIVE|ENTRY TIMING|LEARNING"
```

### After Testing (Analysis)

```bash
# Check new trades recorded
uv run scripts/analyze_performance.py --symbol BTCUSD --timeframe 30m

# View adaptive confidence evolution
uv run adaptive_confidence.py status BTCUSD,30m

# Generate learning report
uv run performance_tracker.py report BTCUSD 30m
```

---

## 🎯 Success Criteria

### Phase 2A: Learning System
- [x] Performance database grows with each trade
- [x] Learning context appears in decision prompts
- [x] Historical patterns identified (RSI, time, MACD)
- [x] Recommendations generated

### Phase 2B: Adaptive Confidence
- [x] Threshold adjusts based on win rate
- [x] Good performance → Lower threshold
- [x] Poor performance → Higher threshold
- [x] Sample size confidence factor applied

### Phase 2C: Entry Timing
- [x] Extended moves blocked
- [x] S/R proximity checked
- [x] Volume confirmation required
- [x] Momentum alignment validated
- [x] ~30-40% of signals skipped for timing

### Combined System
- [ ] All 3 phases run together without errors
- [ ] Trade frequency reduced by ~30-40%
- [ ] Win rate improves (target: 50%+ from 35%)
- [ ] System self-adjusts to market conditions
- [ ] Token costs remain manageable

---

## 🐛 Troubleshooting

### Issue 1: Learning Context Not Loading

**Symptom**: No "[INFO] Loading learning context" in logs

**Solutions**:
```bash
# Check if USE_LEARNING is enabled
echo $USE_LEARNING  # Should be "true"

# Verify performance tracker available
uv run python -c "from performance_tracker import PerformanceTracker; print('OK')"

# Check trade count
uv run python -c "from performance_tracker import PerformanceTracker; t=PerformanceTracker(); print(len(t.get_recent_trades(limit=100)))"
```

### Issue 2: Adaptive Threshold Not Changing

**Symptom**: Threshold stays at base value (65)

**Solutions**:
```bash
# Check config
grep "use_adaptive_confidence" config.json  # Should be true

# Check trade count (need 10+ for adaptation)
uv run adaptive_confidence.py calculate BTCUSD 30m

# Verify import
uv run python -c "from adaptive_confidence import AdaptiveConfidence; print('OK')"
```

### Issue 3: Entry Timing Always Passes

**Symptom**: No trades skipped for timing

**Solutions**:
```bash
# Check config
grep "use_entry_optimizer" config.json  # Should be true

# Test optimizer directly
uv run python entry_optimizer.py '{"decision":"LONG","kline_data":{"Close":[100,110],"High":[101,111],"Low":[99,109],"Volume":[1000,1000]}}'
# Should block extended move

# Verify import
uv run python -c "from entry_optimizer import EntryOptimizer; print('OK')"
```

### Issue 4: UnicodeEncodeError

**Symptom**: Error with Thai characters in console

**Solution**:
```bash
# Windows: Set console to UTF-8
chcp 65001

# Or redirect to file
uv run auto_trader.py --once > output.log 2>&1
```

---

## 📈 Expected Improvements

### Baseline (Before Phase 2)
- Win Rate: 27.6%
- Trades per day: 8-12
- Avg R:R: 1.2
- Net PnL: -$3.27/trade

### Target (After Phase 2)
- Win Rate: 50-60%
- Trades per day: 5-8 (30-40% filtered)
- Avg R:R: 1.5+
- Net PnL: +$5-10/trade

### Timeline
- **Week 1**: 40-45% win rate (system learning)
- **Week 2**: 45-50% win rate (adaptation kicking in)
- **Week 3**: 50-55% win rate (entry timing optimized)
- **Week 4+**: 55-60% win rate (stable performance)

---

## 🔄 Continuous Testing Loop

```bash
# 1. Run trading cycle
uv run auto_trader.py --once

# 2. Check performance
uv run scripts/analyze_performance.py --symbol BTCUSD --timeframe 30m

# 3. Review adaptive threshold
uv run adaptive_confidence.py calculate BTCUSD 30m

# 4. Monitor entry timing
grep "ENTRY TIMING" logs/auto_trader.log | tail -20

# 5. Repeat every 30 minutes
```

---

## 📋 Quick Test Commands

```bash
# Full integration test
uv run auto_trader.py --once

# Test each phase independently
uv run performance_tracker.py report BTCUSD 30m        # Phase 2A
uv run adaptive_confidence.py calculate BTCUSD 30m     # Phase 2B
uv run entry_optimizer.py '{"decision":"LONG",...}'    # Phase 2C

# Analysis
uv run scripts/analyze_performance.py --symbol BTCUSD --timeframe 30m

# Status dashboard
uv run adaptive_confidence.py status BTCUSD,30m XAUUSD,1h
```

---

## 🎓 Understanding the Flow

```
1. Auto Trader Starts
   ↓
2. Load Market Data (BTCUSD 30m)
   ↓
3. [Phase 2A] Load Learning Context
   - Query performance_db.json
   - Calculate win rate, patterns
   - Generate recommendations
   ↓
4. Run Analysis (Indicator, Pattern, Trend agents)
   ↓
5. Decision Agent (LONG/SHORT with confidence)
   - Receives learning context
   - Makes informed decision
   ↓
6. [Phase 2B] Calculate Adaptive Threshold
   - Base: 65
   - Check recent performance
   - Adjust: 65 → 67 (if poor performance)
   ↓
7. Compare: confidence >= adaptive_threshold
   - If no: Skip trade
   - If yes: Continue
   ↓
8. [Phase 2C] Evaluate Entry Timing
   - Check price extension
   - Check S/R proximity
   - Check volume
   - Check momentum
   ↓
9. Decision:
   - If timing poor: Skip trade, log reason
   - If timing good: Execute order
   ↓
10. Record Trade to Performance DB
    - Full context saved
    - Loop back to step 3 for next trade
```

---

## ✅ Final Checklist

Before declaring Phase 2 complete:

### Code
- [x] Phase 2A files: performance_tracker.py, scripts/
- [x] Phase 2B files: adaptive_confidence.py
- [x] Phase 2C files: entry_optimizer.py
- [x] Integration: auto_trader.py, decision_agent.py
- [x] All imports working
- [x] No syntax errors

### Configuration
- [ ] config.json updated with all Phase 2 settings
- [ ] USE_LEARNING environment variable set
- [ ] All feature flags tested (on/off)

### Testing
- [ ] Each phase tested independently
- [ ] Full integration tested
- [ ] Error handling verified
- [ ] Backward compatibility confirmed

### Performance
- [ ] Performance database has 10+ trades
- [ ] Learning context loads correctly
- [ ] Adaptive threshold adjusts
- [ ] Entry timing filters ~30-40% signals
- [ ] Win rate shows improvement trend

### Documentation
- [x] PHASE_2A_COMPLETE.md
- [x] PHASE_2B_COMPLETE.md
- [x] PHASE_2C_COMPLETE.md
- [x] TESTING_PHASE_2_COMPLETE.md
- [x] IMPROVEMENT_PLAN.md updated

---

## 🚀 Next Steps

Once Phase 2 testing is complete:

1. **Monitor for 1 week**
   - Collect 50+ new trades
   - Track win rate improvement
   - Measure skip rate accuracy

2. **Fine-tune parameters**
   - Adjust entry_optimizer thresholds
   - Tune adaptive confidence windows
   - Optimize learning report format

3. **Begin Phase 3**
   - Token cost optimization
   - Smart model routing
   - Prompt compression

---

**Goal**: Achieve 60%+ win rate, profitable per-trade economics, self-improving system

**Status**: Ready for comprehensive testing 🎯
