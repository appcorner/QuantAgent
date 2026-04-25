#property strict
#property description "Adaptive Trailing Lock EA — Multi-Symbol (ported from mt5_adaptive_tl.py)"

#include <Trade/Trade.mqh>

//--- General settings
input bool   InpEnableEA                      = true;  // Enable/disable EA
input int    InpPollIntervalSeconds           = 5;     // Check positions every N seconds
input bool   InpManageOnlyMagic               = false; // If true, only manage positions with matching magic number
input long   InpMagicNumber                   = 0;     // Magic number to filter positions (if InpManageOnlyMagic=true)
input int    InpMaxSlippagePoints             = 30;    // Max slippage for close/modify orders (points)

//--- Symbol filter (comma-separated, e.g. "BTCUSD,EURUSD". Leave empty = all symbols.)
input string InpSymbolFilter                  = "";    // Symbols to manage; empty = all

//--- Stage trigger thresholds (USD profit)
input double InpBornBETriggerUSD              = 5.0;   // Enter born_be stage at this profit
input double InpBornBELockUSD                 = 1.0;   // Lock profit at this amount in born_be
input double InpPreBETriggerUSD               = 20.0;  // Enter pre_be stage at this profit
input double InpPreBELockUSD                  = 5.0;   // Lock profit at this amount in pre_be
input double InpBETriggerUSD                  = 50.0;  // Enter be stage at this profit
input double InpBELockUSD                     = 30.0;  // Lock profit at this amount in be
input double InpTLTriggerUSD                  = 70.0;  // Enter tl (trailing lock) stage at this profit
input double InpTLLockUSD                     = 50.0;  // Lock profit at this amount in tl
input double InpTPTrailTriggerUSD             = 80.0;  // Enter tp_trail stage at this profit
input double InpTPTrailLockUSD                = 60.0;  // Lock profit at this amount in tp_trail

//--- High-track and keep-distance settings
input double InpHighTrackRetracePct           = 30.0;  // Close if profit retraces by this % in tp_trail stage
input bool   InpBelowBornKeepDistanceEnabled  = true;  // In below_born_be: shift SL to preserve distance on new high

//--- ─────────────────────────────────────────
enum ATLStage
{
   STAGE_BELOW_BORN_BE = 0,
   STAGE_BORN_BE,
   STAGE_PRE_BE,
   STAGE_BE,
   STAGE_TL,
   STAGE_TP_TRAIL
};

struct ATLState
{
   ulong    ticket;
   string   symbol;
   int      side;          // 1 = BUY, -1 = SELL
   double   entry_price;
   double   current_price;
   double   current_profit_usd;
   double   best_profit_usd;
   double   best_price;
   double   current_sl;
   double   current_tp;
   int      current_stage;
   bool     stage_unlocked;
   double   locked_profit_usd;
   bool     dynamic_lock_follow;
   bool     high_track_active;
   datetime opened_at;
   datetime last_updated;
};

//--- Globals
CTrade    g_trade;
ATLState  g_states[];
string    g_symbol_filter[];   // parsed list, empty = all

//--- ─────────────────────────────────────────
string SideToString(const int side)
{
   return (side == 1 ? "BUY" : "SELL");
}

string StageToString(const int stage)
{
   switch(stage)
   {
      case STAGE_BORN_BE:  return "born_be";
      case STAGE_PRE_BE:   return "pre_be";
      case STAGE_BE:       return "be";
      case STAGE_TL:       return "tl";
      case STAGE_TP_TRAIL: return "tp_trail";
      default:             return "below_born_be";
   }
}

bool SymbolAllowed(const string symbol)
{
   if(ArraySize(g_symbol_filter) == 0)
      return true;

   for(int i = 0; i < ArraySize(g_symbol_filter); i++)
   {
      if(g_symbol_filter[i] == symbol)
         return true;
   }
   return false;
}

int DetermineStage(const double profit)
{
   if(profit >= InpTPTrailTriggerUSD) return STAGE_TP_TRAIL;
   if(profit >= InpTLTriggerUSD)      return STAGE_TL;
   if(profit >= InpBETriggerUSD)      return STAGE_BE;
   if(profit >= InpPreBETriggerUSD)   return STAGE_PRE_BE;
   if(profit >= InpBornBETriggerUSD)  return STAGE_BORN_BE;
   return STAGE_BELOW_BORN_BE;
}

double GetLockTargetForStage(const int stage)
{
   switch(stage)
   {
      case STAGE_BORN_BE:  return InpBornBELockUSD;
      case STAGE_PRE_BE:   return InpPreBELockUSD;
      case STAGE_BE:       return InpBELockUSD;
      case STAGE_TL:       return InpTLLockUSD;
      case STAGE_TP_TRAIL: return InpTPTrailLockUSD;
      default:             return 0.0;
   }
}

int FindStateByTicket(const ulong ticket)
{
   const int n = ArraySize(g_states);
   for(int i = 0; i < n; i++)
      if(g_states[i].ticket == ticket)
         return i;
   return -1;
}

int EnsureState(const ulong ticket, const string symbol, const int side, const double entry_price)
{
   int idx = FindStateByTicket(ticket);
   if(idx >= 0)
      return idx;

   idx = ArraySize(g_states);
   ArrayResize(g_states, idx + 1);

   g_states[idx].ticket           = ticket;
   g_states[idx].symbol           = symbol;
   g_states[idx].side             = side;
   g_states[idx].entry_price      = entry_price;
   g_states[idx].current_price    = 0.0;
   g_states[idx].current_profit_usd = 0.0;
   g_states[idx].best_profit_usd  = 0.0;
   g_states[idx].best_price       = 0.0;
   g_states[idx].current_sl       = 0.0;
   g_states[idx].current_tp       = 0.0;
   g_states[idx].current_stage    = STAGE_BELOW_BORN_BE;
   g_states[idx].stage_unlocked   = false;
   g_states[idx].locked_profit_usd = 0.0;
   g_states[idx].dynamic_lock_follow = false;
   g_states[idx].high_track_active = false;
   g_states[idx].opened_at        = TimeCurrent();
   g_states[idx].last_updated     = TimeCurrent();

   Print("[ATL] New position: ", symbol, " ticket=", (string)ticket,
         " side=", SideToString(side), " entry=", DoubleToString(entry_price, 5));
   return idx;
}

void RemoveStateAt(const int idx)
{
   const int n = ArraySize(g_states);
   if(idx < 0 || idx >= n)
      return;

   for(int i = idx; i < n - 1; i++)
      g_states[i] = g_states[i + 1];

   ArrayResize(g_states, n - 1);
}

//--- ─────────────────────────────────────────
double ProfitPerPriceUnit(const double entry, const double mark, const double profit_usd)
{
   const double move = MathAbs(mark - entry);
   if(move <= 0.0)
      return 0.0;

   return MathAbs(profit_usd) / move;
}

double ConvertLockedProfitToSL(const string symbol,
                               const int side,
                               const double entry_price,
                               const double current_price,
                               const double locked_profit_usd,
                               const double current_profit_usd)
{
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   const double pppu = ProfitPerPriceUnit(entry_price, current_price, current_profit_usd);
   if(pppu <= 0.0)
      return entry_price;

   const double move = locked_profit_usd / pppu;
   if(move <= 0.0)
      return entry_price;

   const double sl = (side == 1) ? (entry_price + move) : (entry_price - move);
   return NormalizeDouble(sl, digits);
}

double CalculateDynamicLockFromBest(const string symbol,
                                    const int side,
                                    const double entry_price,
                                    const double best_price,
                                    const double best_profit_usd,
                                    const double current_price)
{
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   const double pppu = ProfitPerPriceUnit(entry_price, best_price, best_profit_usd);
   if(pppu <= 0.0)
      return entry_price;

   const double move = best_profit_usd / pppu;
   if(move <= 0.0)
      return entry_price;

   const double sl = (side == 1) ? (entry_price + move) : (entry_price - move);

   if(side == 1 && sl >= current_price)
      return entry_price;
   if(side == -1 && sl <= current_price)
      return entry_price;

   return NormalizeDouble(sl, digits);
}

bool ShouldCloseOnRetrace(const double best_profit, const double current_profit)
{
   if(best_profit <= 0.0)
      return false;

   return ((best_profit - current_profit) / best_profit * 100.0) >= InpHighTrackRetracePct;
}

bool IsSLImproved(const int side, const double new_sl, const double current_sl)
{
   return (side == 1) ? (new_sl > current_sl) : (new_sl < current_sl);
}

bool ModifyPositionSLTP(const ulong ticket, const string symbol, const double new_sl, const double current_tp)
{
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);

   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);

   req.action   = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol   = symbol;
   req.sl       = NormalizeDouble(new_sl, digits);
   req.tp       = (current_tp > 0.0 ? NormalizeDouble(current_tp, digits) : 0.0);

   if(!OrderSend(req, res))
   {
      Print("[ATL] SLTP send failed: ", symbol, " ticket=", (string)ticket, " err=", (string)GetLastError());
      return false;
   }

   if(res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED)
   {
      Print("[ATL] SLTP rejected: ", symbol, " ticket=", (string)ticket,
            " retcode=", (string)res.retcode, " ", res.comment);
      return false;
   }

   return true;
}

bool ClosePositionByTicket(const ulong ticket, const string symbol)
{
   if(!g_trade.PositionClose(ticket, InpMaxSlippagePoints))
   {
      Print("[ATL] Close failed: ", symbol, " ticket=", (string)ticket,
            " retcode=", (string)g_trade.ResultRetcode());
      return false;
   }
   return true;
}

//--- ─────────────────────────────────────────
void ProcessTicket(const ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
      return;

   const string symbol = PositionGetString(POSITION_SYMBOL);

   if(!SymbolAllowed(symbol))
      return;

   if(InpManageOnlyMagic)
   {
      const long magic = PositionGetInteger(POSITION_MAGIC);
      if(magic != InpMagicNumber)
         return;
   }

   const long type_raw        = PositionGetInteger(POSITION_TYPE);
   const int  side            = (type_raw == POSITION_TYPE_BUY ? 1 : -1);
   const double entry_price   = PositionGetDouble(POSITION_PRICE_OPEN);
   const double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
   double current_sl          = PositionGetDouble(POSITION_SL);
   const double current_tp    = PositionGetDouble(POSITION_TP);
   const double current_profit = PositionGetDouble(POSITION_PROFIT);

   if(entry_price <= 0.0 || current_price <= 0.0)
   {
      Print("[ATL] Invalid prices: ", symbol, " ticket=", (string)ticket);
      return;
   }

   if(current_tp <= 0.0)
   {
      Print("[ATL] No TP set: ", symbol, " ticket=", (string)ticket);
      return;
   }

   if(side == 1 && current_tp <= entry_price)
   {
      Print("[ATL] TP invalid for BUY: ", symbol, " ticket=", (string)ticket);
      return;
   }

   if(side == -1 && current_tp >= entry_price)
   {
      Print("[ATL] TP invalid for SELL: ", symbol, " ticket=", (string)ticket);
      return;
   }

   int idx = EnsureState(ticket, symbol, side, entry_price);

   if(g_states[idx].side != side || MathAbs(g_states[idx].entry_price - entry_price) > 1e-8)
   {
      g_states[idx].symbol           = symbol;
      g_states[idx].side             = side;
      g_states[idx].entry_price      = entry_price;
      g_states[idx].current_price    = 0.0;
      g_states[idx].best_profit_usd  = 0.0;
      g_states[idx].best_price       = 0.0;
      g_states[idx].current_sl       = 0.0;
      g_states[idx].current_tp       = 0.0;
      g_states[idx].current_stage    = STAGE_BELOW_BORN_BE;
      g_states[idx].stage_unlocked   = false;
      g_states[idx].locked_profit_usd = 0.0;
      g_states[idx].high_track_active = false;
      g_states[idx].opened_at        = TimeCurrent();
      Print("[ATL] State reset: ", symbol, " ticket=", (string)ticket,
            " side=", SideToString(side), " entry=", DoubleToString(entry_price, 5));
   }

   const double prev_best_profit = g_states[idx].best_profit_usd;
   const double prev_best_price  = g_states[idx].best_price;
   bool has_new_best = false;

   if(current_profit > g_states[idx].best_profit_usd)
   {
      g_states[idx].best_profit_usd = current_profit;
      g_states[idx].best_price      = current_price;
      has_new_best = true;
      Print("[ATL] High-water mark: ", symbol, " ticket=", (string)ticket,
            " best=", DoubleToString(g_states[idx].best_profit_usd, 2));
   }

   g_states[idx].current_price       = current_price;
   g_states[idx].current_profit_usd  = current_profit;
   g_states[idx].current_sl          = current_sl;
   g_states[idx].current_tp          = current_tp;
   g_states[idx].last_updated        = TimeCurrent();

   const int current_stage = DetermineStage(current_profit);

   if(current_stage != g_states[idx].current_stage)
   {
      Print("[ATL] Stage transition: ", symbol, " ticket=", (string)ticket,
            " ", StageToString(g_states[idx].current_stage), " -> ", StageToString(current_stage));
      g_states[idx].current_stage  = current_stage;
      g_states[idx].stage_unlocked = false;
   }

   if(current_stage != STAGE_BELOW_BORN_BE)
   {
      const double lock_target = GetLockTargetForStage(current_stage);
      if(!g_states[idx].stage_unlocked && current_profit >= lock_target)
      {
         g_states[idx].stage_unlocked    = true;
         g_states[idx].locked_profit_usd = lock_target;
         Print("[ATL] Stage unlocked: ", symbol, " ticket=", (string)ticket,
               " stage=", StageToString(current_stage), " lock=", DoubleToString(lock_target, 2));
      }
   }

   double working_sl = current_sl;

   //--- Stage-lock SL
   if(g_states[idx].locked_profit_usd > 0.0)
   {
      const double new_sl = ConvertLockedProfitToSL(symbol, side, entry_price,
                                                    current_price,
                                                    g_states[idx].locked_profit_usd,
                                                    current_profit);

      if(IsSLImproved(side, new_sl, working_sl))
      {
         if(ModifyPositionSLTP(ticket, symbol, new_sl, current_tp))
         {
            Print("[ATL] SL modified (stage lock): ", symbol, " ticket=", (string)ticket,
                  " old=", DoubleToString(working_sl, 5), " new=", DoubleToString(new_sl, 5));
            working_sl = new_sl;
         }
      }
   }

   g_states[idx].dynamic_lock_follow = false;

   //--- below_born_be keep-distance trail
   if(InpBelowBornKeepDistanceEnabled
      && current_stage == STAGE_BELOW_BORN_BE
      && has_new_best
      && working_sl > 0.0
      && prev_best_profit > 0.0)
   {
      const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      double shifted_sl = working_sl;

      if(side == 1)
      {
         const double delta = current_price - prev_best_price;
         shifted_sl = NormalizeDouble(working_sl + MathMax(delta, 0.0), digits);
      }
      else
      {
         const double delta = prev_best_price - current_price;
         shifted_sl = NormalizeDouble(working_sl - MathMax(delta, 0.0), digits);
      }

      const bool sl_valid = (side == 1 ? shifted_sl < current_price : shifted_sl > current_price);
      if(sl_valid && IsSLImproved(side, shifted_sl, working_sl))
      {
         if(ModifyPositionSLTP(ticket, symbol, shifted_sl, current_tp))
         {
            g_states[idx].dynamic_lock_follow = true;
            Print("[ATL] Keep-distance trail: ", symbol, " ticket=", (string)ticket,
                  " old=", DoubleToString(working_sl, 5), " new=", DoubleToString(shifted_sl, 5),
                  " best=", DoubleToString(g_states[idx].best_profit_usd, 2));
            working_sl = shifted_sl;
         }
      }
   }

   //--- Dynamic high-water lock (stages above below_born_be)
   if(current_stage != STAGE_BELOW_BORN_BE && g_states[idx].best_profit_usd > 0.0)
   {
      const double dynamic_sl = CalculateDynamicLockFromBest(symbol, side, entry_price,
                                                             g_states[idx].best_price,
                                                             g_states[idx].best_profit_usd,
                                                             current_price);

      if(IsSLImproved(side, dynamic_sl, working_sl))
      {
         if(ModifyPositionSLTP(ticket, symbol, dynamic_sl, current_tp))
         {
            g_states[idx].dynamic_lock_follow = true;
            Print("[ATL] Dynamic lock follow: ", symbol, " ticket=", (string)ticket,
                  " old=", DoubleToString(working_sl, 5), " new=", DoubleToString(dynamic_sl, 5),
                  " best=", DoubleToString(g_states[idx].best_profit_usd, 2));
            working_sl = dynamic_sl;
         }
      }
   }

   //--- High-track & retrace close
   const bool high_track_active = (current_stage == STAGE_TP_TRAIL && g_states[idx].high_track_active);

   if(current_stage == STAGE_TP_TRAIL && !g_states[idx].high_track_active)
   {
      g_states[idx].high_track_active = true;
      Print("[ATL] High-track enabled: ", symbol, " ticket=", (string)ticket);
   }

   if(high_track_active && ShouldCloseOnRetrace(g_states[idx].best_profit_usd, current_profit))
   {
      Print("[ATL] Retrace triggered: ", symbol, " ticket=", (string)ticket,
            " best=", DoubleToString(g_states[idx].best_profit_usd, 2),
            " current=", DoubleToString(current_profit, 2),
            " retrace_pct=", DoubleToString(InpHighTrackRetracePct, 1));

      if(ClosePositionByTicket(ticket, symbol))
         Print("[ATL] Position closed (retrace): ", symbol, " ticket=", (string)ticket);
      else
         Print("[ATL] Close retrace failed: ", symbol, " ticket=", (string)ticket);
   }

   g_states[idx].current_sl = working_sl;
}

//--- ─────────────────────────────────────────
void CleanupClosedStates()
{
   for(int i = ArraySize(g_states) - 1; i >= 0; i--)
   {
      const ulong  ticket = g_states[i].ticket;
      const string symbol = g_states[i].symbol;

      if(!PositionSelectByTicket(ticket))
      {
         Print("[ATL] Position removed: ", symbol, " ticket=", (string)ticket);
         RemoveStateAt(i);
         continue;
      }

      if(InpManageOnlyMagic)
      {
         const long magic = PositionGetInteger(POSITION_MAGIC);
         if(magic != InpMagicNumber)
         {
            RemoveStateAt(i);
            continue;
         }
      }
   }
}

void ProcessAllPositions()
{
   if(!InpEnableEA)
      return;

   const int total = PositionsTotal();
   for(int i = total - 1; i >= 0; i--)
   {
      const ulong ticket = PositionGetTicket(i);
      if(ticket == 0)
         continue;

      ProcessTicket(ticket);
   }

   CleanupClosedStates();
}

//--- ─────────────────────────────────────────
void ParseSymbolFilter()
{
   ArrayResize(g_symbol_filter, 0);
   if(StringLen(StringTrimRight(StringTrimLeft(InpSymbolFilter))) == 0)
      return;

   string parts[];
   const int n = StringSplit(InpSymbolFilter, ',', parts);
   ArrayResize(g_symbol_filter, n);
   for(int i = 0; i < n; i++)
   {
      g_symbol_filter[i] = StringTrimRight(StringTrimLeft(parts[i]));
   }
}

int OnInit()
{
   ParseSymbolFilter();
   g_trade.SetDeviationInPoints(InpMaxSlippagePoints);
   EventSetTimer(MathMax(1, InpPollIntervalSeconds));

   const string filter_info = (ArraySize(g_symbol_filter) == 0 ? "ALL" : InpSymbolFilter);
   Print("[ATL] EA started — symbols: ", filter_info, " poll=", (string)InpPollIntervalSeconds, "s");
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("[ATL] EA stopped, reason=", (string)reason);
}

void OnTick() { /* logic runs on timer */ }

void OnTimer()
{
   ProcessAllPositions();
}
