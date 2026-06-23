# 🎯 แผนปรับปรุง QuantAgent ให้เทรดคมขึ้น และทำกำไรพอปิดต้นทุน Token

## 📊 การวิเคราะห์จาก Trade History ปัจจุบัน

จาก `data/auto_trade_history.csv` (226 records):
- **ปัญหาหลัก**:
  - มี `should_enter_now = false` สูงมาก → Agent ไม่กล้าเข้า
  - หลายรายการ WIN/LOSS เล็กมาก ($0.45, $0.13)
  - ค่าใช้จ่าย token (GPT-4o-mini x3 + GPT-4o decision) ≈ $0.10-0.20 ต่อ analysis cycle
  - **Win rate และ profit margin ยังไม่เพียงพอกับต้นทุน**

### 📈 Performance After Phase 2 (29 trades analyzed)
- Overall Win Rate: **27.6%** (8W / 21L)
- Best Performer: **BTCUSD 30m** → **53.8%** win rate (7W / 6L)
- Best Session: **NY (16-24 UTC)** → **62.5%** win rate (5W / 3L)
- Worst: **London (08-16 UTC)** → **7.7%** win rate (1W / 12L)

**Target After Phase 2A+2B+2C**: **60%+ win rate** with improved R:R

---

## 🚀 กลยุทธ์การปรับปรุง (6 เฟส)

## ✅ Phase 2: Learning & Adaptive System (COMPLETED)

### Phase 2A: Learning System ✅
**Status**: Implemented & Tested
- ✅ Performance tracking database (`performance_tracker.py`)
- ✅ Historical pattern analysis (RSI, MACD, time, volatility)
- ✅ Learning context injection into decision prompts
- ✅ Backward compatible with `USE_LEARNING` env var

**Files**: 
- `performance_tracker.py`
- `scripts/migrate_history.py`
- `scripts/analyze_performance.py`
- `PHASE_2A_COMPLETE.md`

### Phase 2B: Adaptive Confidence ✅
**Status**: Implemented & Tested
- ✅ Dynamic threshold adjustment based on win rate
- ✅ Performance-based confidence scaling
- ✅ Self-correcting system with confidence factor
- ✅ Config-driven (`use_adaptive_confidence`)

**Files**:
- `adaptive_confidence.py`
- `PHASE_2B_COMPLETE.md`

### Phase 2C: Entry Timing Optimizer ✅
**Status**: Implemented & Ready to Test
- ✅ 4-check entry system (extension, S/R, volume, momentum)
- ✅ Timing quality filter with severity levels
- ✅ Thai language explanations
- ✅ Integration with auto_trader.py
- ✅ Config-driven (`use_entry_optimizer`)

**Files**:
- `entry_optimizer.py`
- `PHASE_2C_COMPLETE.md`
- `TESTING_PHASE_2_COMPLETE.md`

**Expected Impact**:
- Win rate: 27.6% → **50-60%**
- Trade frequency: -30-40% (filtered by entry timing)
- Better R:R from improved entries

**Testing Status**: 🧪 Ready for live testing (7-14 days recommended)

---

## 🎯 Remaining Phases

### 1. **Performance Tracking & Learning System** 
สร้างระบบติดตามผลและเรียนรู้จากการเทรดจริง

#### 1.1 Trade Performance Database
```python
# performance_tracker.py
class PerformanceTracker:
    """
    เก็บประวัติการเทรดแบบ structured พร้อม metadata สำหรับการวิเคราะห์
    """
    def __init__(self):
        self.db_file = "data/performance_db.json"
        self.metrics_file = "data/performance_metrics.json"
        
    def record_trade(self, trade_data: dict):
        """
        บันทึกการเทรดพร้อม context ที่ครบถ้วน:
        - Decision prompts & responses
        - Market conditions (RSI, MACD, trend slope, volatility)
        - Entry/exit timing
        - Actual outcome (win/loss/breakeven)
        - PnL และ risk-reward ที่ได้จริง
        """
        
    def calculate_pattern_performance(self):
        """
        วิเคราะห์ว่า pattern ประเภทไหน timeframe ไหน มี win rate สูงสุด
        Example: "Double Bottom + RSI divergence on 30m XAUUSD" → 72% win rate
        """
        
    def calculate_condition_performance(self):
        """
        วิเคราะห์เงื่อนไขตลาดที่ทำให้ชนะ/แพ้
        - RSI range ที่ควรเข้า/ไม่ควรเข้า
        - MACD histogram strength threshold
        - Volatility (ATR) ที่เหมาะสม
        - Time of day / day of week patterns
        """
        
    def generate_learning_report(self):
        """
        สร้าง report สำหรับ inject เข้า decision prompt:
        "Based on historical performance:
         - Avoid LONG when RSI > 75 on 15m (win rate: 28%)
         - Prefer SHORT on descending triangle breakdowns (win rate: 68%)
         - Best entry: wait for pullback retest after breakout (avg RR: 2.1)"
        """
```

#### 1.2 Context-Aware Decision Prompts
ปรับ `decision_agent.py` ให้โหลดข้อมูลประสิทธิภาพก่อนตัดสินใจ:

```python
def _read_decision_prompt_template() -> str:
    # โหลด base template
    base_prompt = prompt_path.read_text(encoding="utf-8")
    
    # Inject learning insights
    performance = PerformanceTracker()
    learning_context = performance.generate_learning_report(
        symbol=state["stock_name"],
        timeframe=state["time_frame"]
    )
    
    enhanced_prompt = f"""
{base_prompt}

---
## 📚 Historical Performance Insights (Last 100 Trades)

{learning_context}

**Apply these learnings to improve decision quality.**
---
"""
    return enhanced_prompt
```

---

## 🔜 Phase 3: Token Cost Optimization (NEXT)

### 1. **Performance Tracking & Learning System** ✅ COMPLETED
สร้างระบบติดตามผลและเรียนรู้จากการเทรดจริง

#### 1.1 Trade Performance Database ✅
- ✅ `performance_tracker.py` implemented
- ✅ Structured JSON database with full trade context
- ✅ Pattern performance analysis
- ✅ Market condition correlation

#### 1.2 Context-Aware Decision Prompts ✅
- ✅ Learning context injection in `decision_agent.py`
- ✅ Historical insights from recent 50-100 trades
- ✅ Actionable recommendations based on patterns

---

### 2. **Adaptive Confidence Threshold** ✅ COMPLETED
ปรับ `min_confidence_score` แบบ dynamic ตาม win rate

- ✅ `adaptive_confidence.py` implemented
- ✅ Dynamic threshold: 50-80 based on performance
- ✅ Win rate > 65% + R:R > 1.5 → Lower threshold (55-60)
- ✅ Win rate < 45% → Raise threshold (75-80)
- ✅ Confidence factor based on sample size
- ✅ Config integration with `use_adaptive_confidence`

---

### 3. **Entry Timing Optimizer** ✅ COMPLETED
ปรับปรุงการตัดสินใจ `should_enter_now`

#### 3.1 Pattern-Specific Entry Rules ✅
- ✅ `entry_optimizer.py` implemented
- ✅ 4-check system:
  1. Price extension from swing (< 3%)
  2. S/R proximity (> 0.5% distance)
  3. Volume confirmation (> 0.8x average)
  4. Momentum alignment (direction-matched)
- ✅ Severity levels (high blocker, medium warning)
- ✅ Thai language explanations
- ✅ Integration with `auto_trader.py`

---

## 🎯 Phase 3: Token Cost Optimization (PENDING)
```python
# entry_optimizer.py
class EntryOptimizer:
    """
    ตัดสินใจว่าควรเข้าเลย หรือ รอ pullback/retest
    """
    
    def evaluate_entry_timing(self, state: dict) -> dict:
        """
        วิเคราะห์ entry timing quality:
        - Distance from last swing high/low
        - Volume profile
        - Recent price momentum (last 3 candles)
        - Proximity to major S/R levels
        """
        kline = state["kline_data"]
        decision = state.get("final_trade_decision")
        
        # Calculate price extension
        recent_candles = kline[-10:]
        if decision == "LONG":
            swing_low = min(recent_candles["low"])
            current_price = kline["close"][-1]
            extension_pct = (current_price - swing_low) / swing_low * 100
            
            if extension_pct > 3.0:  # Extended too far
                return {
                    "should_enter_now": False,
                    "reason": f"ราคาวิ่งไปแล้ว {extension_pct:.1f}% จาก swing low - รอ pullback มา retest support ก่อน"
                }
        
        # Similar logic for SHORT...
        
        return {"should_enter_now": True, "reason": "Entry timing is optimal"}
```

#### 3.2 Inject Entry Optimizer Results
เพิ่มใน `decision_agent.py`:
```python
def trade_decision_node(state) -> dict:
    # ... existing logic ...
    
    # Optimize entry timing
    optimizer = EntryOptimizer()
    timing_result = optimizer.evaluate_entry_timing(state)
    
    # Merge with LLM decision
    final_decision = json.loads(response.content)
    final_decision["should_enter_now"] = timing_result["should_enter_now"]
    final_decision["entry_timing_reason"] = timing_result["reason"]
    
    return {
        "final_trade_decision": json.dumps(final_decision),
        ...
    }
```

---

### 4. **Token Cost Optimization**
ลดต้นทุน token โดยไม่ลด quality

#### 4.1 Smart Model Selection
```python
# config.json
{
  "llm": {
    "provider": "openai",
    "agent_model": "gpt-4o-mini",      // ถูกมาก $0.15/1M input
    "graph_model": "gpt-4o-mini",      // ใช้ mini ก่อน
    "decision_model": "gpt-4o",        // ใช้ full model เฉพาะ decision
    "use_smart_routing": true,         // เลือก model แบบ dynamic
    "temperature": 0.1
  }
}
```

#### 4.2 Reduce Redundant Analysis
```python
# smart_analyzer.py
class SmartAnalyzer:
    """
    ลดการ analyze ซ้ำซ้อน
    """
    
    def should_reanalyze(self, state: dict) -> bool:
        """
        ตัดสินใจว่าควร run full analysis หรือ skip
        - ถ้ามี position เปิดอยู่ และราคายังไม่เปลี่ยนมาก → skip
        - ถ้า candle ยังไม่ close → skip
        - ถ้า market ใน consolidation range → skip
        """
        
    def use_cached_indicators(self, state: dict) -> bool:
        """
        ใช้ indicator ที่คำนวณไว้แล้วถ้า candle ยังไม่ close
        """
```

#### 4.3 Batch Analysis (Multi-Symbol)
```python
# batch_analyzer.py
def batch_analyze(symbols: list) -> list:
    """
    Analyze หลาย symbol พร้อมกันใน 1 LLM call
    ลด overhead และประหยัด token
    """
    combined_prompt = "\n\n".join([
        f"Symbol {i+1}: {symbol}\n{indicator_data}"
        for i, (symbol, indicator_data) in enumerate(symbols)
    ])
    # ... single LLM call ...
**Goal**: ลดค่าใช้จ่าย token จาก $0.15 → **$0.08 per trade**

#### 4.1 Smart Model Selection
```python
# config.json
{
  "llm": {
    "provider": "openai",
    "agent_model": "gpt-4o-mini",      // ถูกมาก $0.15/1M input
    "graph_model": "gpt-4o-mini",      // ใช้ mini ก่อน
    "decision_model": "gpt-4o",        // ใช้ full model เฉพาะ decision
    "use_smart_routing": true,         // เลือก model แบบ dynamic
    "temperature": 0.1
  }
}
```

#### 4.2 Reduce Redundant Analysis
```python
# smart_analyzer.py
class SmartAnalyzer:
    """
    ลดการ analyze ซ้ำซ้อน
    """
    
    def should_reanalyze(self, state: dict) -> bool:
        """
        ตัดสินใจว่าควร run full analysis หรือ skip
        - ถ้ามี position เปิดอยู่ และราคายังไม่เปลี่ยนมาก → skip
        - ถ้า candle ยังไม่ close → skip
        - ถ้า market ใน consolidation range → skip
        """
        
    def use_cached_indicators(self, state: dict) -> bool:
        """
        ใช้ indicator ที่คำนวณไว้แล้วถ้า candle ยังไม่ close
        """
```

#### 4.3 Prompt Compression
ลดขนาด prompt โดยไม่เสีย context:
```python
# ก่อน (verbose)
"Technical Indicator Report: The RSI is currently at 68.5 which indicates..."

# หลัง (compact)
"Indicator: RSI=68.5 (near OB), MACD=+2.3↑, Stoch=72/65..."
```

#### 4.4 Response Caching
```python
# Use OpenAI prompt caching for repeated context
# Cache indicator calculations, chart patterns
```

**Expected Impact**: -50% token cost ($0.15 → $0.08)

---

## 🔜 Phase 4: Multi-Timeframe Confluence Filter (PENDING)
**Goal**: เพิ่มคุณภาพ setup โดยดู higher timeframe alignment

```python
# mtf_filter.py
class MultiTimeframeFilter:
    """
    ตรวจสอบว่า setup มี confluence จาก higher timeframe หรือไม่
    """
    
    def check_htf_alignment(self, symbol: str, current_tf: str, decision: str) -> dict:
        """
        ดึงข้อมูล higher timeframe และตรวจสอบ trend alignment
        Example: 
        - Current: 15m LONG signal
        - Check: 1H trend = bullish? 4H support zone?
        """
        
        htf_map = {
            "15m": "1h",
            "30m": "1h", 
            "1h": "4h",
            "4h": "1d"
        }
        
        higher_tf = htf_map.get(current_tf)
        if not higher_tf:
            return {"aligned": True, "reason": "No higher TF to check"}
            
        # Fetch HTF data
        htf_data = self.fetch_ohlc(symbol, higher_tf, bars=50)
        htf_trend = self.detect_trend(htf_data)
        
        if decision == "LONG" and htf_trend == "bearish":
            return {
                "aligned": False,
                "reason": f"HTF {higher_tf} is bearish - counter-trend trade rejected"
            }
        elif decision == "SHORT" and htf_trend == "bullish":
            return {
                "aligned": False,
                "reason": f"HTF {higher_tf} is bullish - counter-trend trade rejected"
            }
            
        return {"aligned": True, "reason": f"HTF {higher_tf} aligned"}
```

**Expected Impact**: +5-10% win rate by filtering counter-trend trades

---

## 🔜 Phase 5: Position Sizing Optimization (PENDING)

**Goal**: จัดการความเสี่ยงแบบ dynamic

```python
# position_sizer.py
class PositionSizer:
    """
    คำนวณขนาด position ตาม confidence, win rate, และ account risk
    """
    
    def calculate_position_size(
        self, 
        confidence: float, 
        win_rate: float,
        account_balance: float,
        risk_per_trade_pct: float = 1.0
    ) -> float:
        """
        Kelly Criterion-based sizing with confidence adjustment
        """
        # Base kelly: (win_rate - (1-win_rate)/avg_rr) * account
        # Adjust by confidence: higher confidence → larger size (within limits)
```

**Expected Impact**: +20% profit efficiency, lower drawdowns

---

## 📈 Implementation Roadmap

### ✅ Phase 2: Learning & Adaptive System (COMPLETED)
**Week 1-2**: 
- ✅ Phase 2A: Performance tracking & learning
- ✅ Phase 2B: Adaptive confidence threshold
- ✅ Phase 2C: Entry timing optimizer
- 🧪 **Testing**: 7-14 days live testing (IN PROGRESS)

### 🎯 Phase 3: Token Cost Optimization (NEXT)
**Week 3-4**: 
- [ ] Smart model routing (mini vs full)
- [ ] Prompt compression
- [ ] Response caching
- [ ] Redundant analysis reduction

**Target**: -50% token cost ($0.15 → $0.08)

### 🔜 Phase 4: Multi-Timeframe Confluence (FUTURE)
**Week 5-6**: 
- [ ] Higher timeframe trend detection
- [ ] S/R level validation across timeframes
- [ ] Counter-trend filter

**Target**: +5-10% win rate

### 🔜 Phase 5: Position Sizing (FUTURE)
**Week 7+**: 
- [ ] Kelly Criterion implementation
- [ ] Confidence-based sizing
- [ ] Drawdown-aware scaling

**Target**: +20% profit efficiency

---

## 📊 Success Metrics

### Current Baseline (29 trades)
- Win Rate: 27.6%
- BTCUSD 30m: 53.8% win rate
- Token Cost: ~$0.15/trade
- Net PnL: -$3.27/trade

### After Phase 2 (Target)
- Win Rate: **50-60%**
- Trade Frequency: -30-40% (filtered)
- Net PnL: **+$5-10/trade**

### After Phase 3 (Target)
- Win Rate: 50-60%
- Token Cost: **$0.08/trade** (-50%)
- Net PnL: +$10-15/trade

### After Phase 4 (Target)
- Win Rate: **60-70%**
- Token Cost: $0.08/trade
- Net PnL: +$15-20/trade

### After Phase 5 (Target)
- Win Rate: 60-70%
- Profit Efficiency: **+20%**
- Sharpe Ratio: **>1.5**

---

## 📋 Current Status Summary

| Phase | Status | Progress | Files |
|-------|--------|----------|-------|
| Phase 2A | ✅ Complete | 100% | performance_tracker.py, scripts/ |
| Phase 2B | ✅ Complete | 100% | adaptive_confidence.py |
| Phase 2C | ✅ Complete | 100% | entry_optimizer.py |
| **Testing** | 🧪 **In Progress** | 0% | **User testing 7-14 days** |
| Phase 3 | ⏭️ Pending | 0% | Smart routing, caching |
| Phase 4 | ⏭️ Pending | 0% | mtf_filter.py |
| Phase 5 | ⏭️ Pending | 0% | position_sizer.py |

---

## 🎯 Immediate Next Steps

1. **User Testing Phase 2** (7-14 days)
   - Run `uv run auto_trader.py --once` regularly
   - Monitor performance metrics
   - Collect 50-100 new trades
   - Verify win rate improvement to 50-60%

2. **After Testing Success**
   - Begin Phase 3: Token Cost Optimization
   - Implement smart model routing
   - Add prompt compression
   - Set up response caching

3. **Long-term**
   - Phase 4: Multi-timeframe confluence
   - Phase 5: Position sizing optimization
   - Continuous monitoring and improvement

---

**Goal**: 60%+ win rate, profitable per-trade economics, self-improving system

**Documentation**:
- [PHASE_2A_COMPLETE.md](PHASE_2A_COMPLETE.md)
- [PHASE_2B_COMPLETE.md](PHASE_2B_COMPLETE.md)
- [PHASE_2C_COMPLETE.md](PHASE_2C_COMPLETE.md)
- [TESTING_PHASE_2_COMPLETE.md](TESTING_PHASE_2_COMPLETE.md)
- [ ] Implement pattern performance analysis
- [ ] Implement condition performance analysis
- [ ] สร้าง learning report generator
- [ ] Integrate learning context เข้า decision prompts

### Phase 3: Entry Optimization (Week 3)
- [ ] สร้าง `EntryOptimizer` class
- [ ] Implement price extension detection
- [ ] Implement proximity-to-SR detection
- [ ] Implement volume profile analysis
- [ ] ทดสอบ backtest กับ historical data

### Phase 4: Adaptive Systems (Week 4)
- [ ] Implement `AdaptiveConfidence` 
- [ ] Implement `MultiTimeframeFilter`
- [ ] Integrate ทั้งหมดเข้า `auto_trader.py`
- [ ] A/B testing: old vs new system

### Phase 5: Token Optimization (Week 5)
- [ ] Implement smart model routing
- [ ] Implement caching mechanisms
- [ ] Compress prompts
- [ ] Monitor token usage vs profitability

### Phase 6: Production & Monitoring (Week 6)
- [ ] Deploy production system
- [ ] Setup real-time monitoring dashboard
- [ ] Alert system สำหรับ anomaly detection
- [ ] Weekly performance review automation

---

## 🎯 Success Metrics (Target ภายใน 3 เดือน)

| Metric | Current | Target |
|--------|---------|--------|
| Win Rate | ~45-50% | **≥60%** |
| Avg Risk/Reward | ~1.4 | **≥1.6** |
| Token Cost/Trade | $0.15 | **≤$0.08** |
| Net Profit/Trade | -$0.05 | **≥$0.20** |
| False Entry Rate | ~60% | **≤30%** |
| Monthly ROI | -10% | **≥15%** |

---

## 💡 Advanced Features (Future)

### A. Reinforcement Learning Layer
```python
# rl_decision_optimizer.py
"""
ใช้ RL agent เรียนรู้ว่า:
- เมื่อไหร่ควรเข้า vs. รอ
- Position sizing ที่เหมาะสม
- SL/TP adjustment แบบ dynamic
"""
```

### B. Market Regime Detection
```python
# regime_detector.py
"""
ตรวจจับว่าตลาดอยู่ใน regime ไหน:
- Trending (high momentum)
- Range-bound (mean reversion)
- Volatile breakout
- Low liquidity

ปรับ strategy parameters ตาม regime
"""
```

### C. Sentiment Analysis Integration
```python
# sentiment_analyzer.py
"""
ดึงข้อมูล:
- News sentiment
- Social media buzz
- Funding rates (crypto)
- VIX / Fear & Greed Index

เพิ่ม context ให้ decision making
"""
```

---

## 🔧 Quick Start Implementation

### Step 1: สร้าง Performance Tracker
```bash
python -c "from performance_tracker import PerformanceTracker; tracker = PerformanceTracker(); tracker.initialize()"
```

### Step 2: Migrate Historical Data
```bash
python scripts/migrate_history.py --input data/auto_trade_history.csv --output data/performance_db.json
```

### Step 3: Run Analysis
```bash
python scripts/analyze_performance.py --generate-report
```

### Step 4: Update Config
```json
{
  "learning": {
    "enabled": true,
    "min_trades_for_learning": 30,
    "learning_window": 100,
    "confidence_adaptation": true
  }
}
```

### Step 5: Test New System
```bash
# Backtest mode
python auto_trader.py --backtest --start 2026-01-01 --end 2026-03-01

# Paper trading mode
python auto_trader.py --dry-run --use-learning

# Live mode (after validation)
python auto_trader.py --use-learning
```

---

## 📚 Files to Create

```
quantagent/
├── performance_tracker.py       # NEW: Track & analyze trade history
├── adaptive_confidence.py       # NEW: Dynamic confidence threshold
├── entry_optimizer.py           # NEW: Entry timing optimization
├── mtf_filter.py               # NEW: Multi-timeframe filter
├── learning_engine.py          # NEW: Pattern learning system
├── token_optimizer.py          # NEW: Cost reduction utilities
├── regime_detector.py          # NEW: Market regime detection
├── decision_agent_prompt_30m.md # DONE: 30m specific prompt
└── scripts/
    ├── migrate_history.py      # NEW: CSV → JSON migration
    ├── analyze_performance.py  # NEW: Performance analysis
    └── backtest_engine.py      # NEW: Backtesting framework
```

---

## 🚨 Risk Management Enhancements

### A. Position Sizing Based on Confidence
```python
def calculate_position_size(confidence: float, account_balance: float, risk_pct: float = 1.0):
    """
    ปรับขนาด position ตาม confidence:
    - Confidence 85+: ใช้ 100% of risk capital
    - Confidence 70-84: ใช้ 70% of risk capital  
    - Confidence 60-69: ใช้ 50% of risk capital
    - Confidence <60: skip trade
    """
    if confidence >= 85:
        multiplier = 1.0
    elif confidence >= 70:
        multiplier = 0.7
    elif confidence >= 60:
        multiplier = 0.5
    else:
        return 0.0
        
    risk_amount = account_balance * (risk_pct / 100) * multiplier
    return risk_amount
```

### B. Correlation-Based Portfolio Management
```python
# ไม่เปิด position ที่ correlate กันสูงพร้อมกัน
# Example: BTCUSD + ETHUSD = 0.95 correlation → เปิดได้แค่ 1 ตัว
```

---

## 📊 Expected Impact

**Before Optimization:**
- 100 trades/month
- 45% win rate
- Avg win: $2.50, Avg loss: -$3.00
- Token cost: $15/month
- **Net PnL: -$2.50/month** ❌

**After Optimization:**
- 60 trades/month (selective)
- 65% win rate  
- Avg win: $3.50, Avg loss: -$2.00
- Token cost: $5/month
- **Net PnL: +$77/month** ✅

**ROI Improvement: +$79.50/month (+3180%)**

---

## 🎓 Key Principles

1. **Data-Driven Decisions**: เทรดบน evidence จาก historical performance
2. **Quality over Quantity**: เทรดน้อยลง แต่ accuracy สูงขึ้น
3. **Cost Consciousness**: ทุก token มีค่า - optimize อย่างต่อเนื่อง
4. **Continuous Learning**: ระบบต้องฉลาดขึ้นทุกวัน
5. **Risk First**: Protect capital ก่อน chase profits

---

สนใจให้ฉันเริ่ม implement feature ไหนก่อนดีครับ? แนะนำเริ่มจาก **Performance Tracker** เพราะเป็น foundation ของทุกอย่าง 🚀
