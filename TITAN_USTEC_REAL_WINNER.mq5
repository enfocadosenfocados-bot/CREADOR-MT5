//+------------------------------------------------------------------+
//|                                TITAN_USTEC_PROFITABLE.mq5        |
//|                                  Copyright 2026, Antigravity AI  |
//|                         https://antigravity.ai/trading-systems   |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, Antigravity AI"
#property link        "https://antigravity.ai"
#property version     "4.10"
#property description "TITAN USTEC PROFITABLE: Institutional Pullback with Asymmetric PnL."
#property strict

#include <Trade\Trade.mqh>
#include <Trade\OrderInfo.mqh>
#include <Trade\PositionInfo.mqh>

CTrade         trades;
COrderInfo     order;
CPositionInfo  position;

//+------------------------------------------------------------------+
//| INPUTS                                                           |
//+------------------------------------------------------------------+
input group "=== GESTION DE CAPITAL Y HORARIOS ==="
input double   InpLots                    = 1.0;          // Volumen de lote fijo
input int      InpSpreadMaxPoints         = 5000;         // Spread maximo permitido
input int      InpStartHour               = 2;            // Hora inicio operativa (servidor)
input int      InpEndHour                 = 18;           // Hora fin operativa (servidor)
input ulong    InpMagicNumber             = 20261023;     // Magic Number unico

input group "=== FILTRO DE MACRO-TENDENCIA HTF ==="
input bool     InpUseTrendFilter          = true;         // Activar filtro H1 200 EMA
input ENUM_TIMEFRAMES InpTrendTimeframe   = PERIOD_H1;    // Timeframe macro
input int      InpTrendEMAPeriod          = 200;          // Periodo EMA macro

input group "=== DETECCION CUANTITATIVA ==="
input double   InpATRMultiplier           = 2.20;         // Multiplicador ATR vela gatillo
input double   InpMinCandlePoints         = 80.0;         // Minimo puntos de vela
input double   InpMaxCandlePoints         = 800.0;        // Maximo puntos de vela
input int      InpMaxConsecutiveLosses    = 2;            // Maximo perdidas antes de pausa
input int      InpCooldownHours           = 4;            // Horas de pausa

input group "=== GESTION ASIMETRICA DE BENEFICIOS ==="
input bool     InpUsePartialClose         = true;         // Cierre parcial 50%
input int      InpPartialTriggerPoints    = 5000;         // Puntos para parcial (+50.0 pts)
input double   InpPartialCloseRatio       = 0.50;         // 50% de la posicion
input int      InpTakeProfitPoints        = 12000;        // Take Profit final (+120.0 pts = +$120 USD)

input group "=== STOP LOSS REALISTA Y TRAILING RESILIENTE ==="
input int      InpMinLossPoints           = 2000;         // Stop Loss minimo (20.0 pts)
input int      InpMaxLossPoints           = 3000;         // Stop Loss maximo (30.0 pts)
input double   InpSlDistanceRatio         = 0.90;         // Ratio SL
input double   InpTriggerATRMultiplier    = 0.25;         // Gatillo ATR

input bool     InpUseBreakeven            = true;         // Activar Breakeven
input int      InpBreakevenTriggerPoints  = 2500;         // Puntos para BE (+25.0 pts)
input int      InpBreakevenLockPoints     = 300;          // Puntos asegurados (+3.0 pts)

input bool     InpUseTrailingStop         = true;         // Trailing Stop amplio (solo para runner)
input int      InpTrailingStartPoints     = 5500;         // Iniciar trailing SOLO tras superar parcial (+55.0 pts)
input int      InpTrailDistancePoints     = 3000;         // Distancia de trailing amplia (30.0 pts fuera del ruido)

input bool     InpUsePendingExpiry        = true;         // Cancelar pendientes
input int      InpPendingExpiryMinutes    = 20;           // Minutos maximos
input bool     InpCloseFriday             = true;         // Cierre de viernes
input int      InpFridayCloseHour         = 17;           // Hora de cierre viernes

// Variables internas
double   point_value = 0.0;
datetime last_signal_bar_time = 0;
int      atr_handle   = INVALID_HANDLE;
int      trend_handle = INVALID_HANDLE;
int      consecutive_losses = 0;
datetime last_cooldown_until = 0;

int OnInit()
{
   trades.SetExpertMagicNumber(InpMagicNumber);
   trades.SetMarginMode();
   trades.SetTypeFillingBySymbol(_Symbol);

   point_value = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   if(point_value <= 0.0) point_value = 1.0;

   atr_handle = iATR(_Symbol, PERIOD_CURRENT, 14);

   if(InpUseTrendFilter)
      trend_handle = iMA(_Symbol, InpTrendTimeframe, InpTrendEMAPeriod, 0, MODE_EMA, PRICE_CLOSE);

   return(INIT_SUCCEEDED);
}

void OnDeinit(const int reason)
{
   if(atr_handle   != INVALID_HANDLE) IndicatorRelease(atr_handle);
   if(trend_handle != INVALID_HANDLE) IndicatorRelease(trend_handle);
}

double GetATRPoints()
{
   double atr_buf[];
   ArraySetAsSeries(atr_buf, true);
   if(CopyBuffer(atr_handle, 0, 0, 1, atr_buf) <= 0) return 0.0;
   return atr_buf[0] / point_value;
}

double CandleBodyPoints(int shift)
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   if(CopyRates(_Symbol, PERIOD_CURRENT, shift, 1, rates) <= 0) return 0.0;
   return (rates[0].close - rates[0].open) / point_value;
}

void ManageOpenPositions()
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double vol_step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double vol_min  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   if(vol_step <= 0.0) vol_step = 0.01;
   if(vol_min <= 0.0) vol_min = 0.01;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() != _Symbol || position.Magic() != InpMagicNumber) continue;

      ulong  ticket     = position.Ticket();
      double open_price = position.PriceOpen();
      double current_sl = position.StopLoss();
      double cur_vol    = position.Volume();

      if(position.PositionType() == POSITION_TYPE_BUY)
      {
         double profit_pts = (tick.bid - open_price) / point_value;

         // Cierre parcial 50% al alcanzar Target 1
         if(InpUsePartialClose && cur_vol >= InpLots && profit_pts >= InpPartialTriggerPoints)
         {
            double close_vol = MathFloor((cur_vol * InpPartialCloseRatio) / vol_step) * vol_step;
            if(close_vol >= vol_min && (cur_vol - close_vol) >= vol_min)
            {
               if(trades.PositionClosePartial(ticket, close_vol))
               {
                  double be_sl = open_price + (InpBreakevenLockPoints * point_value);
                  trades.PositionModify(ticket, be_sl, position.TakeProfit());
                  continue;
               }
            }
         }

         // Breakeven
         if(InpUseBreakeven && profit_pts >= InpBreakevenTriggerPoints)
         {
            double desired_sl = open_price + (InpBreakevenLockPoints * point_value);
            if(current_sl < desired_sl)
               trades.PositionModify(ticket, desired_sl, position.TakeProfit());
         }

         // Trailing Robusto SOLO despues de superar Target 1
         if(InpUseTrailingStop && profit_pts >= InpTrailingStartPoints)
         {
            double new_sl = tick.bid - (InpTrailDistancePoints * point_value);
            double be_min = open_price + (InpBreakevenLockPoints * point_value);
            if(new_sl < be_min) new_sl = be_min;

            if(new_sl > current_sl + (50 * point_value))
               trades.PositionModify(ticket, new_sl, position.TakeProfit());
         }
      }
      else if(position.PositionType() == POSITION_TYPE_SELL)
      {
         double profit_pts = (open_price - tick.ask) / point_value;

         // Cierre parcial 50% al alcanzar Target 1
         if(InpUsePartialClose && cur_vol >= InpLots && profit_pts >= InpPartialTriggerPoints)
         {
            double close_vol = MathFloor((cur_vol * InpPartialCloseRatio) / vol_step) * vol_step;
            if(close_vol >= vol_min && (cur_vol - close_vol) >= vol_min)
            {
               if(trades.PositionClosePartial(ticket, close_vol))
               {
                  double be_sl = open_price - (InpBreakevenLockPoints * point_value);
                  trades.PositionModify(ticket, be_sl, position.TakeProfit());
                  continue;
               }
            }
         }

         // Breakeven
         if(InpUseBreakeven && profit_pts >= InpBreakevenTriggerPoints)
         {
            double desired_sl = open_price - (InpBreakevenLockPoints * point_value);
            if(current_sl == 0.0 || current_sl > desired_sl)
               trades.PositionModify(ticket, desired_sl, position.TakeProfit());
         }

         // Trailing Robusto SOLO despues de superar Target 1
         if(InpUseTrailingStop && profit_pts >= InpTrailingStartPoints)
         {
            double new_sl = tick.ask + (InpTrailDistancePoints * point_value);
            double be_max = open_price - (InpBreakevenLockPoints * point_value);
            if(new_sl > be_max) new_sl = be_max;

            if(current_sl == 0.0 || new_sl < current_sl - (50 * point_value))
               trades.PositionModify(ticket, new_sl, position.TakeProfit());
         }
      }
   }
}

void ManagePendingOrders(int trigger_points)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!order.SelectByIndex(i)) continue;
      if(order.Symbol() != _Symbol || order.Magic() != InpMagicNumber) continue;

      ulong ticket = order.Ticket();
      if(InpUsePendingExpiry)
      {
         datetime setup_time = (datetime)order.TimeSetup();
         if(setup_time > 0 && (TimeCurrent() - setup_time) >= (InpPendingExpiryMinutes * 60))
         {
            trades.OrderDelete(ticket);
            continue;
         }
      }
   }
}

void PlaceBuyStop(int trigger_points)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double distance = trigger_points * point_value;
   double price    = tick.ask + distance;

   double raw_sl_pts = (distance / point_value) * InpSlDistanceRatio;
   double sl_dist_pts = MathMax((double)InpMinLossPoints, MathMin((double)InpMaxLossPoints, raw_sl_pts));
   double sl = price - (sl_dist_pts * point_value);
   double tp = price + (InpTakeProfitPoints * point_value);

   trades.BuyStop(InpLots, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "TITAN_USTEC_BUY");
}

void PlaceSellStop(int trigger_points)
{
   MqlTick tick;
   if(!SymbolInfoTick(_Symbol, tick)) return;

   double distance = trigger_points * point_value;
   double price    = tick.bid - distance;

   double raw_sl_pts = (distance / point_value) * InpSlDistanceRatio;
   double sl_dist_pts = MathMax((double)InpMinLossPoints, MathMin((double)InpMaxLossPoints, raw_sl_pts));
   double sl = price + (sl_dist_pts * point_value);
   double tp = price - (InpTakeProfitPoints * point_value);

   trades.SellStop(InpLots, price, _Symbol, sl, tp, ORDER_TIME_GTC, 0, "TITAN_USTEC_SELL");
}

void CloseAllOrdersAndPositions(string reason)
{
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!order.SelectByIndex(i)) continue;
      if(order.Symbol() == _Symbol && order.Magic() == InpMagicNumber)
         trades.OrderDelete(order.Ticket());
   }
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() == _Symbol && position.Magic() == InpMagicNumber)
         trades.PositionClose(position.Ticket());
   }
}

int CountOwnPendingOrders(ENUM_ORDER_TYPE order_type)
{
   int count = 0;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
   {
      if(!order.SelectByIndex(i)) continue;
      if(order.Symbol() == _Symbol && order.Magic() == InpMagicNumber && order.OrderType() == order_type)
         count++;
   }
   return count;
}

int CountOwnPositions()
{
   int count = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!position.SelectByIndex(i)) continue;
      if(position.Symbol() == _Symbol && position.Magic() == InpMagicNumber)
         count++;
   }
   return count;
}

void OnTick()
{
   MqlDateTime now;
   TimeToStruct(TimeCurrent(), now);

   if(InpCloseFriday && now.day_of_week == 5 && now.hour >= InpFridayCloseHour)
   {
      CloseAllOrdersAndPositions("Cierre preventivo de Viernes");
      return;
   }

   double atr_points    = GetATRPoints();
   double filter_points = atr_points * InpATRMultiplier;
   int    trigger_points = (int)MathRound(MathMax(5.0, atr_points * InpTriggerATRMultiplier));
   double candle_points  = CandleBodyPoints(0);

   int buy_stops  = CountOwnPendingOrders(ORDER_TYPE_BUY_STOP);
   int sell_stops = CountOwnPendingOrders(ORDER_TYPE_SELL_STOP);
   int positions  = CountOwnPositions();

   ManageOpenPositions();
   ManagePendingOrders(trigger_points);

   if(now.hour < InpStartHour || now.hour >= InpEndHour) return;
   if((int)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) > InpSpreadMaxPoints) return;

   datetime current_bar_time = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(current_bar_time == last_signal_bar_time) return;

   // Filtro Macro H1 EMA200
   double trend_ema = 0.0;
   double trend_buf[];
   ArraySetAsSeries(trend_buf, true);
   if(trend_handle != INVALID_HANDLE && CopyBuffer(trend_handle, 0, 0, 1, trend_buf) == 1)
      trend_ema = trend_buf[0];

   MqlTick tick;
   SymbolInfoTick(_Symbol, tick);

   if(candle_points <= -filter_points && buy_stops == 0 && positions == 0)
   {
      if(!InpUseTrendFilter || (trend_ema > 0.0 && tick.ask > trend_ema))
      {
         PlaceBuyStop(trigger_points);
         last_signal_bar_time = current_bar_time;
      }
   }

   if(candle_points >= filter_points && sell_stops == 0 && positions == 0)
   {
      if(!InpUseTrendFilter || (trend_ema > 0.0 && tick.bid < trend_ema))
      {
         PlaceSellStop(trigger_points);
         last_signal_bar_time = current_bar_time;
      }
   }
}
//+------------------------------------------------------------------+
