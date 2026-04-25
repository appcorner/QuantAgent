#property strict
#property description "Adaptive Trailing Lock EA (ported from mt5_adaptive_tl.py)"

#include <Trade/Trade.mqh>

//--- General settings
input bool   InpEnableEA                     = true;  // Enable/disable EA
input int    InpPollIntervalSeconds          = 5;     // Check positions every N seconds
input bool   InpManageOnlyMagic              = false; // If true, only manage positions with matching magic number
input long   InpMagicNumber                  = 0;     // Magic number to filter positions (if InpManageOnlyMagic=true)
input int    InpMaxSlippagePoints            = 30;    // Max slippage for close/modify orders (points)

//--- Stage trigger thresholds (USD)
input double InpBornBETriggerUSD             = 5.0;   // Enter born_be stage at this profit
input double InpBornBELockUSD                = 1.0;   // Lock profit at this amount in born_be
input double InpPreBETriggerUSD              = 20.0;  // Enter pre_be stage at this profit
input double InpPreBELockUSD                 = 5.0;   // Lock profit at this amount in pre_be
input double InpBETriggerUSD                 = 50.0;  // Enter be stage at this profit
input double InpBELockUSD                    = 30.0;  // Lock profit at this amount in be
input double InpTLTriggerUSD                 = 70.0;  // Enter tl (trailing lock) stage at this profit
input double InpTLLockUSD                    = 50.0;  // Lock profit at this amount in tl
input double InpTPTrailTriggerUSD            = 80.0;  // Enter tp_trail stage at this profit
input double InpTPTrailLockUSD               = 60.0;  // Lock profit at this amount in tp_trail

//--- High-track and keep-distance settings
input double InpHighTrackRetracePct          = 30.0;  // Close trade if profit retraces by this % in tp_trail stage
input bool   InpBelowBornKeepDistanceEnabled = true;  // In below_born_be: shift SL to preserve distance on new high-water mark

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
   int      side; // 1 = BUY, -1 = SELL
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

CTrade g_trade;
ATLState g_states[];

string SideToString(const int side)
{
   return (side == 1 ? "BUY" : "SELL");
}

string StageToString(const int stage)
{
   switch(stage)
   {
      case STAGE_BORN_BE:      return "born_be";
      case STAGE_PRE_BE:       return "pre_be";
      case STAGE_BE:           return "be";
      case STAGE_TL:           return "tl";
      case STAGE_TP_TRAIL:     return "tp_trail";
      default:                 return "below_born_be";
   }
}

int DetermineStage(const double current_profit_usd)
{
   if(current_profit_usd >= InpTPTrailTriggerUSD) return STAGE_TP_TRAIL;
   if(current_profit_usd >= InpTLTriggerUSD)      return STAGE_TL;
   if(current_profit_usd >= InpBETriggerUSD)      return STAGE_BE;
   if(current_profit_usd >= InpPreBETriggerUSD)   return STAGE_PRE_BE;
   if(current_profit_usd >= InpBornBETriggerUSD)  return STAGE_BORN_BE;
   return STAGE_BELOW_BORN_BE;
}

double GetLockTargetForStage(const int stage)
{
   switch(stage)
   {
      case STAGE_BORN_BE:   return InpBornBELockUSD;
      case STAGE_PRE_BE:    return InpPreBELockUSD;
      case STAGE_BE:        return InpBELockUSD;
      case STAGE_TL:        return InpTLLockUSD;
      case STAGE_TP_TRAIL:  return InpTPTrailLockUSD;
      default:              return 0.0;
   }
}

int FindStateIndexByTicket(const ulong ticket)
{
   const int n = ArraySize(g_states);
   for(int i = 0; i < n; i++)
   {
      if(g_states[i].ticket == ticket)
         return i;
   }
   return -1;
}

void ResetState(ATLState &s, const ulong ticket, const int side, const double entry_price)
{
   s.ticket = ticket;
   s.side = side;
   s.entry_price = entry_price;
   s.current_price = 0.0;
   s.current_profit_usd = 0.0;
   s.best_profit_usd = 0.0;
   s.best_price = 0.0;
   s.current_sl = 0.0;
   s.current_tp = 0.0;
   s.current_stage = STAGE_BELOW_BORN_BE;
   s.stage_unlocked = false;
   s.locked_profit_usd = 0.0;
   s.dynamic_lock_follow = false;
   s.high_track_active = false;
   s.opened_at = TimeCurrent();
   s.last_updated = TimeCurrent();
}

int EnsureState(const ulong ticket, const int side, const double entry_price)
{
   int idx = FindStateIndexByTicket(ticket);
   if(idx >= 0)
      return idx;

   idx = ArraySize(g_states);
   ArrayResize(g_states, idx + 1);
   ResetState(g_states[idx], ticket, side, entry_price);

   PrintFormat("[ATL] New position detected. ticket=%I64u side=%s entry=%.5f", ticket, SideToString(side), entry_price);
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

double ProfitPerPriceUnit(const double entry_price, const double mark_price, const double profit_usd)
{
   const double price_move = MathAbs(mark_price - entry_price);
   if(price_move <= 0.0)
      return 0.0;

   return MathAbs(profit_usd) / price_move;
}

double ConvertLockedProfitToSL(const int side,
                               const double entry_price,
                               const double current_price,
                               const double locked_profit_usd,
                               const double current_profit_usd)
{
   const double pppu = ProfitPerPriceUnit(entry_price, current_price, current_profit_usd);
   if(pppu <= 0.0)
      return entry_price;

   const double protected_move = locked_profit_usd / pppu;
   if(protected_move <= 0.0)
      return entry_price;

   const double sl = (side == 1) ? (entry_price + protected_move) : (entry_price - protected_move);
   return NormalizeDouble(sl, _Digits);
}

double CalculateDynamicLockFromBest(const int side,
                                    const double entry_price,
                                    const double best_price,
                                    const double best_profit_usd,
                                    const double current_price)
{
   const double pppu = ProfitPerPriceUnit(entry_price, best_price, best_profit_usd);
   if(pppu <= 0.0)
      return entry_price;

   const double protected_move = best_profit_usd / pppu;
   if(protected_move <= 0.0)
      return entry_price;

   const double sl = (side == 1) ? (entry_price + protected_move) : (entry_price - protected_move);

   // Broker-side sanity checks.
   if(side == 1 && sl >= current_price)
      return entry_price;
   if(side == -1 && sl <= current_price)
      return entry_price;

   return NormalizeDouble(sl, _Digits);
}

bool ShouldCloseOnRetrace(const double best_profit_usd, const double current_profit_usd)
{
   if(best_profit_usd <= 0.0)
      return false;

   const double retrace_amount = best_profit_usd - current_profit_usd;
   const double retrace_pct = (retrace_amount / best_profit_usd) * 100.0;
   return retrace_pct >= InpHighTrackRetracePct;
}

bool IsSLImproved(const int side, const double new_sl, const double current_sl)
{
   if(side == 1)
      return new_sl > current_sl;
   return new_sl < current_sl;
}

bool ModifyPositionSLTP(const ulong ticket, const double new_sl, const double current_tp)
{
   MqlTradeRequest req;
   MqlTradeResult  res;
   ZeroMemory(req);
   ZeroMemory(res);

   req.action   = TRADE_ACTION_SLTP;
   req.position = ticket;
   req.symbol   = _Symbol;
   req.sl       = NormalizeDouble(new_sl, _Digits);
   req.tp       = (current_tp > 0.0 ? NormalizeDouble(current_tp, _Digits) : 0.0);

   if(!OrderSend(req, res))
   {
      PrintFormat("[ATL] SLTP send failed. ticket=%I64u err=%d", ticket, GetLastError());
      return false;
   }

   if(res.retcode != TRADE_RETCODE_DONE && res.retcode != TRADE_RETCODE_PLACED)
   {
      PrintFormat("[ATL] SLTP rejected. ticket=%I64u retcode=%d comment=%s", ticket, (int)res.retcode, res.comment);
      return false;
   }

   return true;
}

bool ClosePositionByTicket(const ulong ticket)
{
   if(!g_trade.PositionClose(ticket, InpMaxSlippagePoints))
   {
      PrintFormat("[ATL] Close failed. ticket=%I64u retcode=%d", ticket, (int)g_trade.ResultRetcode());
      return false;
   }
   return true;
}

void ProcessTicket(const ulong ticket)
{
   if(!PositionSelectByTicket(ticket))
      return;

   const string symbol = PositionGetString(POSITION_SYMBOL);
   if(symbol != _Symbol)
      return;

   if(InpManageOnlyMagic)
   {
      const long magic = PositionGetInteger(POSITION_MAGIC);
      if(magic != InpMagicNumber)
         return;
   }

   const long type_raw = PositionGetInteger(POSITION_TYPE);
   const int side = (type_raw == POSITION_TYPE_BUY ? 1 : -1);
   const double entry_price = PositionGetDouble(POSITION_PRICE_OPEN);
   const double current_price = PositionGetDouble(POSITION_PRICE_CURRENT);
   const double current_sl = PositionGetDouble(POSITION_SL);
   const double current_tp = PositionGetDouble(POSITION_TP);
   const double current_profit_usd = PositionGetDouble(POSITION_PROFIT);

   if(entry_price <= 0.0 || current_price <= 0.0)
   {
      PrintFormat("[ATL] %s ticket=%I64u invalid prices", symbol, ticket);
      return;
   }

   if(current_tp <= 0.0)
   {
      PrintFormat("[ATL] %s ticket=%I64u no TP set", symbol, ticket);
      return;
   }

   if(side == 1 && current_tp <= entry_price)
   {
      PrintFormat("[ATL] %s ticket=%I64u TP invalid for BUY", symbol, ticket);
      return;
   }

   if(side == -1 && current_tp >= entry_price)
   {
      PrintFormat("[ATL] %s ticket=%I64u TP invalid for SELL", symbol, ticket);
      return;
   }

   int idx = EnsureState(ticket, side, entry_price);

   // Ticket can be reused after reconnect/restart; reset state if side or entry changes.
   if(g_states[idx].side != side || MathAbs(g_states[idx].entry_price - entry_price) > 1e-8)
   {
      ResetState(g_states[idx], ticket, side, entry_price);
      PrintFormat("[ATL] Reset state. ticket=%I64u side=%s entry=%.5f", ticket, SideToString(side), entry_price);
   }

   const double prev_best_profit_usd = g_states[idx].best_profit_usd;
   const double prev_best_price = g_states[idx].best_price;
   bool has_new_best = false;

   if(current_profit_usd > g_states[idx].best_profit_usd)
   {
      g_states[idx].best_profit_usd = current_profit_usd;
      g_states[idx].best_price = current_price;
      has_new_best = true;
      PrintFormat("[ATL] %s ticket=%I64u new high-water mark %.2f", symbol, ticket, g_states[idx].best_profit_usd);
   }

   g_states[idx].current_price = current_price;
   g_states[idx].current_profit_usd = current_profit_usd;
   g_states[idx].current_sl = current_sl;
   g_states[idx].current_tp = current_tp;
   g_states[idx].last_updated = TimeCurrent();

   const int current_stage = DetermineStage(current_profit_usd);
   if(current_stage != g_states[idx].current_stage)
   {
      PrintFormat("[ATL] %s ticket=%I64u stage transition %s -> %s",
                  symbol,
                  ticket,
                  StageToString(g_states[idx].current_stage),
                  StageToString(current_stage));
      g_states[idx].current_stage = current_stage;
      g_states[idx].stage_unlocked = false;
   }

   if(current_stage != STAGE_BELOW_BORN_BE)
   {
      const double lock_target = GetLockTargetForStage(current_stage);
      if(!g_states[idx].stage_unlocked && current_profit_usd >= lock_target)
      {
         g_states[idx].stage_unlocked = true;
         g_states[idx].locked_profit_usd = lock_target;
         PrintFormat("[ATL] stage_unlocked ticket=%I64u stage=%s lock=%.2f",
                     ticket,
                     StageToString(current_stage),
                     lock_target);
      }
   }

   double working_sl = current_sl;

   if(g_states[idx].locked_profit_usd > 0.0)
   {
      const double new_sl = ConvertLockedProfitToSL(side,
                                                    entry_price,
                                                    current_price,
                                                    g_states[idx].locked_profit_usd,
                                                    current_profit_usd);

      if(IsSLImproved(side, new_sl, working_sl))
      {
         if(ModifyPositionSLTP(ticket, new_sl, current_tp))
         {
            PrintFormat("[ATL] sl_modified ticket=%I64u reason=stage_lock old_sl=%.5f new_sl=%.5f",
                        ticket,
                        working_sl,
                        new_sl);
            working_sl = new_sl;
         }
      }
   }

   g_states[idx].dynamic_lock_follow = false;

   if(InpBelowBornKeepDistanceEnabled
      && current_stage == STAGE_BELOW_BORN_BE
      && has_new_best
      && working_sl > 0.0
      && prev_best_profit_usd > 0.0)
   {
      double shifted_sl = working_sl;
      if(side == 1)
      {
         const double price_delta = current_price - prev_best_price;
         shifted_sl = NormalizeDouble(working_sl + MathMax(price_delta, 0.0), _Digits);
      }
      else
      {
         const double price_delta = prev_best_price - current_price;
         shifted_sl = NormalizeDouble(working_sl - MathMax(price_delta, 0.0), _Digits);
      }

      const bool sl_valid = (side == 1 ? shifted_sl < current_price : shifted_sl > current_price);
      if(sl_valid && IsSLImproved(side, shifted_sl, working_sl))
      {
         if(ModifyPositionSLTP(ticket, shifted_sl, current_tp))
         {
            g_states[idx].dynamic_lock_follow = true;
            PrintFormat("[ATL] keep_distance_trail_follow ticket=%I64u reason=below_born_be_keep_distance old_sl=%.5f new_sl=%.5f best_profit=%.2f",
                        ticket,
                        working_sl,
                        shifted_sl,
                        g_states[idx].best_profit_usd);
            working_sl = shifted_sl;
         }
      }
   }

   if(current_stage != STAGE_BELOW_BORN_BE && g_states[idx].best_profit_usd > 0.0)
   {
      const double dynamic_sl = CalculateDynamicLockFromBest(side,
                                                             entry_price,
                                                             g_states[idx].best_price,
                                                             g_states[idx].best_profit_usd,
                                                             current_price);

      if(IsSLImproved(side, dynamic_sl, working_sl))
      {
         if(ModifyPositionSLTP(ticket, dynamic_sl, current_tp))
         {
            g_states[idx].dynamic_lock_follow = true;
            PrintFormat("[ATL] dynamic_lock_follow ticket=%I64u old_sl=%.5f new_sl=%.5f best_profit=%.2f",
                        ticket,
                        working_sl,
                        dynamic_sl,
                        g_states[idx].best_profit_usd);
            working_sl = dynamic_sl;
         }
      }
   }

   const bool high_track_active = (current_stage == STAGE_TP_TRAIL && g_states[idx].high_track_active);

   if(current_stage == STAGE_TP_TRAIL && !g_states[idx].high_track_active)
   {
      g_states[idx].high_track_active = true;
      PrintFormat("[ATL] high_track_enabled ticket=%I64u", ticket);
   }

   if(high_track_active && ShouldCloseOnRetrace(g_states[idx].best_profit_usd, current_profit_usd))
   {
      PrintFormat("[ATL] retrace_triggered ticket=%I64u best=%.2f current=%.2f retrace_pct=%.2f",
                  ticket,
                  g_states[idx].best_profit_usd,
                  current_profit_usd,
                  InpHighTrackRetracePct);

      if(ClosePositionByTicket(ticket))
      {
         PrintFormat("[ATL] position_closed_retrace ticket=%I64u", ticket);
      }
      else
      {
         PrintFormat("[ATL] close_retrace_failed ticket=%I64u", ticket);
      }
   }

   g_states[idx].current_sl = working_sl;
}

void CleanupClosedStates()
{
   for(int i = ArraySize(g_states) - 1; i >= 0; i--)
   {
      const ulong ticket = g_states[i].ticket;
      if(!PositionSelectByTicket(ticket))
      {
         PrintFormat("[ATL] position_removed ticket=%I64u", ticket);
         RemoveStateAt(i);
         continue;
      }

      const string symbol = PositionGetString(POSITION_SYMBOL);
      if(symbol != _Symbol)
      {
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

int OnInit()
{
   g_trade.SetDeviationInPoints(InpMaxSlippagePoints);
   EventSetTimer(MathMax(1, InpPollIntervalSeconds));
   PrintFormat("[ATL] EA started on %s (poll=%ds)", _Symbol, InpPollIntervalSeconds);
   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   PrintFormat("[ATL] EA stopped. reason=%d", reason);
}

void OnTick()
{
   // Logic runs on timer for deterministic polling cadence.
}

void OnTimer()
{
   ProcessAllPositions();
}
