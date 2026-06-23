# Performance Tracking System - Quick Start Guide (uv edition)

## ขั้นตอนการใช้งานด้วย uv

### 1. Migration (ครั้งแรกเท่านั้น)
แปลง CSV history เป็น JSON database:
```bash
uv run scripts/migrate_history.py
```

### 2. วิเคราะห์ Performance
```bash
# วิเคราะห์ทุก trades
uv run scripts/analyze_performance.py

# วิเคราะห์เฉพาะ symbol
uv run scripts/analyze_performance.py --symbol BTCUSD

# วิเคราะห์เฉพาะ timeframe
uv run scripts/analyze_performance.py --timeframe 30m

# วิเคราะห์ล่าสุด 50 trades
uv run scripts/analyze_performance.py --limit 50
```

### 3. ดู Learning Report
```bash
uv run performance_tracker.py report
uv run performance_tracker.py report XAUUSD
uv run performance_tracker.py report BTCUSD 15m
```

## Key Findings จาก Current Data

### 📊 Overall Statistics (29 completed trades)
- **Win Rate: 27.6%** ⚠️ ต่ำมาก (target: 60%+)
- **Wins: 8 | Losses: 12 | Breakeven: 9**
- **Average Win: $38.19**
- **Average Loss: -$19.07**
- **Expected PnL/Trade: -$3.27** ❌ ขาดทุนต่อเทรด

### 🎯 Performance by Timeframe
- **30m: 53.8% win rate** ✅ ดีที่สุด (13 trades)
- **1h: 8.3% win rate** ❌ แย่มาก (12 trades)
- **15m: 0.0% win rate** ❌ (4 trades)

### ⏰ Performance by Time Session (UTC)
- **New York (16-24): 62.5% win rate** ✅ ดีมาก
- **Asian (00-08): 25.0% win rate** ⚠️
- **London (08-16): 7.7% win rate** ❌ แย่มาก

### 📈 Performance by Symbol
- **BTCUSD: 41.2% win rate** (17 trades, $76.72 PnL)
- **XAUUSD: 25.0% win rate** (4 trades, $0.02 PnL)
- **BTCUSDT: 0.0% win rate** (8 trades, breakeven only - dry run)

## 🚨 Critical Insights

### 1. Confidence Score Issue
- ทุก trades มี confidence 50-60 เท่านั้น (win rate 28%)
- **ต้อง filter trades ที่ confidence < 65 ทิ้ง**

### 2. Timeframe Selection
- **30m ทำงานได้ดีที่สุด** (53.8% win rate)
- 1h และ 15m ควร disable หรือ ปรับ strategy

### 3. Trading Session
- **ควรเทรดช่วง New York session** (16:00-24:00 UTC)
- หลีกเลี่ยง London session (win rate 7.7%)

### 4. Risk Management
- R:R ratio = 0 → ไม่มีข้อมูล SL/TP ที่ชัดเจน
- ต้องบังคับ track actual R:R ใน future trades

## 📝 Running Auto Trader with uv

```bash
# Validate config
uv run auto_trader.py --validate-config

# Run once
uv run auto_trader.py --once

# Run continuously
uv run auto_trader.py
```

## 📝 Next Steps

### Phase 2A: Integrate Learning into Decision Agent (Ready to implement)

1. **Update decision_agent.py** ให้โหลด learning insights:
```python
from performance_tracker import PerformanceTracker

def trade_decision_node(state) -> dict:
    # Load historical performance
    tracker = PerformanceTracker()
    learning_report = tracker.generate_learning_report(
        symbol=state["stock_name"],
        timeframe=state["time_frame"],
        limit=50
    )
    
    # Inject into prompt
    enhanced_prompt = f"""
{base_prompt}

---
## Historical Performance Context

{learning_report}

**Apply these insights to improve your decision quality.**
---
"""
    ...
```

2. **Update auto_trader.py** ให้บันทึก context ครบถ้วน:
```python
# After analysis completes
tracker = PerformanceTracker()
tracker.record_trade({
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "symbol": symbol,
    "timeframe": timeframe,
    "decision": decision,
    "entry_price": entry_price,
    "confidence_score": confidence,
    "risk_reward_ratio": rr_ratio,
    "market_conditions": {
        "rsi": rsi_value,
        "macd": macd_value,
        "atr": atr_value
    },
    "indicator_report": indicator_report,
    "pattern_report": pattern_report,
    "trend_report": trend_report,
    "entry_reason": entry_timing_reason
})
```

3. **Immediate Config Changes** (ใน config.json):
```json
{
  "risk": {
    "min_confidence_score": 65,  // เพิ่มจาก 55
    "min_risk_reward_ratio": 1.5  // เพิ่มจาก 1.2
  },
  "symbols": [
    // Disable 1h และ 15m, เน้น 30m
    {"enabled": true, "timeframe": "30m", ...},
    {"enabled": false, "timeframe": "1h", ...},
    {"enabled": false, "timeframe": "15m", ...}
  ]
}
```

## 📊 Files Created

- `performance_tracker.py` - Core tracking & analysis engine ✅
- `scripts/migrate_history.py` - CSV to JSON migration ✅
- `scripts/analyze_performance.py` - Performance analysis CLI ✅
- `data/performance_db.json` - Structured trade database ✅
- `data/performance_metrics.json` - Aggregated metrics ✅
- `IMPROVEMENT_PLAN.md` - Complete improvement roadmap ✅

## 🎯 Expected Improvements

After implementing Phase 2:
- Win rate: 27.6% → **55-60%** (focus on 30m + high confidence)
- Expected PnL: -$3.27 → **+$5-10/trade**
- Token cost: $0.15 → **$0.10/trade** (with optimization)
- Monthly ROI: -40% → **+20%**

## Development Commands

```bash
# Run web interface
uv run python web_interface.py

# Run MT5 analyzer
uv run python mt5_analyze.py --symbol BTCUSD --timeframe 30m --bars 150

# Run Binance analyzer  
uv run python binance_analyze.py --symbol BTCUSDT --timeframe 1h --bars 100
```

พร้อมไปต่อ Phase 2A หรือยัง? 🚀
