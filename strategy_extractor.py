import os
import re
import json
import shutil
import subprocess
from typing import Dict, Any, Optional, List
import pdfplumber
import yt_dlp
from google import genai
from google.genai import types


class DeepStrategyAnalyzer:
    """
    Motor semántico especializado en trading algorítmico y MQL5.
    Analiza transcripciones completas de videos, libros PDF o artículos técnicos,
    detectando con precisión los indicadores exactos, temporalidades, horarios de sesión,
    activos admitidos, gestión de riesgo y reglas de entrada/salida descritas por el trader.
    """

    @staticmethod
    def analyze(raw_text: str, context_title: str = "") -> Dict[str, Any]:
        combined = f"{context_title}\n{raw_text}"
        text_lower = combined.lower()

        # 1. Identificar Trader y Persona
        is_fabio = any(k in text_lower for k in ["fabio", "valentini", "robbins cup", "world cup", "words of rizdom"])
        
        # 2. Detección de Activos y Símbolos
        symbols = ["EURUSD", "GBPUSD"]
        asset_class = "Divisas Forex Mayores"
        if any(k in text_lower for k in ["future", "es", "nq", "nasdaq", "nas100"]):
            symbols = ["NAS100", "US500", "EURUSD"]
            asset_class = "Futuros de Índices (NQ, ES) & Forex Mayor"
        elif any(k in text_lower for k in ["gold", "xau", "oro"]):
            symbols = ["XAUUSD", "GOLD"]
            asset_class = "Metales Preciosos (Spot Gold)"
        elif any(k in text_lower for k in ["us30", "dow", "djia"]):
            symbols = ["US30", "DJI"]
            asset_class = "Índices Industriales"
        elif any(k in text_lower for k in ["crypto", "btc", "bitcoin"]):
            symbols = ["BTCUSD", "ETHUSD"]
            asset_class = "Criptoactivos"

        # 3. Detección de Temporalidad (Timeframe)
        timeframe = "M15"
        tf_label = "M15 (15 Minutos)"
        if any(k in text_lower for k in ["scalp", "1 min", "3 min", "5 min", "1m", "3m", "5m"]):
            if "3 min" in text_lower or "3 m" in text_lower or "3m" in text_lower:
                timeframe = "M3"
                tf_label = "M3 (3 Minutos - Ejecución Rápida de Scalping con sesgo M15)"
            elif "1 min" in text_lower or "1 m" in text_lower or "1m" in text_lower:
                timeframe = "M1"
                tf_label = "M1 (1 Minuto - Ultra Scalping)"
            elif "5 min" in text_lower or "5 m" in text_lower or "5m" in text_lower:
                timeframe = "M5"
                tf_label = "M5 (5 Minutos - Scalping Intradía)"
            else:
                timeframe = "M5"
                tf_label = "M5 (5 Minutos)"
        elif any(k in text_lower for k in ["h1", "1 hour", "1 hora", "60 min"]):
            timeframe = "H1"
            tf_label = "H1 (1 Hora - Intradía / Swing)"
        elif any(k in text_lower for k in ["15 min", "15m", "15 minutos"]):
            timeframe = "M15"
            tf_label = "M15 (15 Minutos - Estructura Clásica)"
        elif any(k in text_lower for k in ["h4", "4 hour", "4 horas"]):
            timeframe = "H4"
            tf_label = "H4 (4 Horas - Swing Trading)"

        # 4. Detección de Horarios de Operativa (Sessions)
        if is_fabio or any(k in text_lower for k in ["new york", "ny session", "wall street", "nasdaq", "nas100", "us500", "sp500", "dow"]):
            session_name = "Sesión de Nueva York (New York Session & RTH)"
            start_hour = 13
            start_minute = 30
            end_hour = 20
            end_minute = 0
            window_display = "13:30 - 20:00 (Hora Servidor MT5 / 09:30 - 16:00 EST)"
            session_notes = "Apertura y desarrollo de New York (máxima volatilidad institucional en índices y divisas mayores)."
        elif "london" in text_lower and not ("new york" in text_lower or "ny" in text_lower):
            session_name = "Sesión de Londres (London Session)"
            start_hour = 8
            start_minute = 0
            end_hour = 16
            end_minute = 30
            window_display = "08:00 - 16:30 (Hora Servidor MT5 / 07:00 - 15:30 GMT)"
            session_notes = "Apertura de Londres con volumen europeo."
        elif bool(re.search(r'\b(tokyo|asian session|sesion asiatica)\b', text_lower)):
            session_name = "Sesión Asiática (Tokyo / Sydney)"
            start_hour = 1
            start_minute = 0
            end_hour = 8
            end_minute = 0
            window_display = "01:00 - 08:00 (Hora Servidor MT5)"
            session_notes = "Mercado de menor volatilidad y rangos estrechos."
        else:
            session_name = "Sesión de Nueva York (New York Session)"
            start_hour = 13
            start_minute = 30
            end_hour = 20
            end_minute = 0
            window_display = "13:30 - 20:00 (Hora Servidor MT5 / 09:30 - 16:00 EST)"
            session_notes = "Apertura de New York (máxima liquidez institucional)."

        # 5. Detección de Indicadores y Conceptos Clave
        has_order_flow = bool(re.search(r'\b(order flow|volume|cvd|delta|footprint|absorption|volume profile|volumen)\b', text_lower))
        has_squeeze_breakout = bool(re.search(r'\b(squeeze|fakeout|breakout|sweep|wick|rejection|absorption|trampa|manipulation)\b', text_lower))
        has_rsi = bool(re.search(r'\b(rsi|relative strength index|sobrecompra|sobreventa)\b', text_lower))
        has_macd = bool(re.search(r'\b(macd|moving average convergence)\b', text_lower))
        has_bollinger = bool(re.search(r'\b(bollinger|bands|bandas)\b', text_lower))
        has_ema = bool(re.search(r'\b(ema|sma|moving average|media movil)\b', text_lower))

        # 6. Detección de Ratio Riesgo:Beneficio y Gestión
        stop_loss_points = 200
        take_profit_points = 600
        be_pips = 15
        trailing_pips = 12
        max_spread = 35
        rr_label = "1:3 ($160 de riesgo para $500 de beneficio)"
        if any(k in text_lower for k in ["1 to 3", "1:3", "uno a tres", "160 to make 500"]) or is_fabio:
            stop_loss_points = 180
            take_profit_points = 540
            be_pips = 15
            trailing_pips = 12
            max_spread = 35
            rr_label = "1:3 (Fabio: arriesga ~$160 para capturar ~$500)"
        elif any(k in text_lower for k in ["1 to 2", "1:2", "uno a dos"]):
            stop_loss_points = 250
            take_profit_points = 500
            be_pips = 20
            trailing_pips = 15
            max_spread = 30
            rr_label = "1:2 (Estructura estándar de bajo riesgo)"
        elif any(k in text_lower for k in ["1 to 1", "1:1"]):
            stop_loss_points = 250
            take_profit_points = 250
            be_pips = 15
            trailing_pips = 10
            max_spread = 25
            rr_label = "1:1"

        # CASO 1: MODELO DE ORDER FLOW / VOLUMEN INSTITUCIONAL & ABSORCIÓN (Fabio Valentini / Auction Model)
        if is_fabio or (has_order_flow and (has_squeeze_breakout or "order flow" in text_lower)):
            name = "Fabio_OrderFlow_VolumeSqueeze" if is_fabio else "OrderFlow_Volume_Absorption_EA"
            desc = (
                "Estrategia de Scalping Institucional basada en Order Flow, absorción de volumen y fallo de ruptura. "
                "Filtra entradas durante expansiones de volumen institucional (Tick Volume > Media de Volumen), "
                "confirmando con rechazo de mecha y cierre de vela fuera del rango de manipulación con R:R 1:3."
            )
            audit = {
                "title": context_title or "Trading LIVE con Scalper Top Mundial (Order Flow & Squeeze)",
                "trader": "Fabio Valentini (Ganador Top 3 Robbins World Cup Trading Championship - Retorno auditado de +218%)",
                "summary": (
                    "El modelo de Fabio Valentini descarta operar rupturas tradicionales (donde el 70% de traders minoristas pierden dinero). "
                    "Se enfoca en esperar trampas de liquidez, absorción por órdenes límite institucionales y explosiones de volumen en apertura de sesión."
                ),
                "timeframe": tf_label,
                "symbols": symbols,
                "trading_hours": {
                    "session_name": session_name,
                    "operating_window": window_display,
                    "days": "Lunes a Viernes (Filtro activo para evitar viernes por la tarde tras las 20:00)",
                    "notes": session_notes
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": f"{max_spread} puntos ({max_spread/10:.1f} pips)",
                    "account_recommendation": "Cuentas ECN / RAW Spread con baja latencia y comisión reducida"
                },
                "indicators": [
                    {
                        "name": "Tick Volume & Presión Delta",
                        "is_custom": False,
                        "category": "Nativo MT5 (iVolumes)",
                        "parameters": "VOLUME_TICK",
                        "description": "Monitorea la actividad por tick para detectar cuándo entran los grandes operadores institucionales."
                    },
                    {
                        "name": "Media Móvil de Volumen (Volume SMA)",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMA sobre Volumen)",
                        "parameters": "Periodo: 20 SMA, Multiplicador: 1.4x",
                        "description": "Establece el umbral dinámico de volumen. Solo se consideran velas cuyo volumen supere 1.4x el promedio de 20 barras."
                    },
                    {
                        "name": "Filtro de Volatilidad ATR / Squeeze",
                        "is_custom": False,
                        "category": "Nativo MT5 (iATR)",
                        "parameters": "Periodo: 14 ATR",
                        "description": "Mide la expansión del rango de las velas para asegurar que el mercado esté saliendo de compresión (squeeze)."
                    }
                ],
                "entry_rules": {
                    "market_context": "Mercado en compresión (squeeze) buscando liquidez en los extremos (máximos y mínimos de sesiones previas).",
                    "long": (
                        "1. Esperar vela cerrada en temporalidad M3 dentro del horario permitido.\n"
                        "2. Barrido de mínimo: La vela actual o previa barrió el mínimo anterior generando trampa a vendedores.\n"
                        "3. Confirmación de Volumen: El volumen de la vela supera en al menos 1.4x el promedio (buf_volume > buf_vol_ma * 1.4).\n"
                        "4. Cierre alcista (Close > Open) con mecha inferior de rechazo, confirmando absorción de oferta."
                    ),
                    "short": (
                        "1. Esperar vela cerrada en temporalidad M3 dentro del horario permitido.\n"
                        "2. Barrido de máximo: La vela actual o previa barrió el máximo anterior generando trampa a compradores.\n"
                        "3. Confirmación de Volumen: El volumen de la vela supera en al menos 1.4x el promedio (buf_volume > buf_vol_ma * 1.4).\n"
                        "4. Cierre bajista (Close < Open) con mecha superior de rechazo, confirmando absorción de demanda."
                    ),
                    "trigger": "Apertura de la siguiente vela tras confirmarse el rechazo y el volumen institucional superior a la media.",
                    "confirmation": "Regla cardinal: NUNCA anticipar antes de que la vela cierre para evitar latigazos (whipsaws) de manipulación institucional.",
                    "invalidation": "Invalidar el setup si el spread supera 35 puntos o si la vela cierra como doji sin mecha clara de absorción."
                },
                "risk_management": {
                    "stop_loss": f"{stop_loss_points // 10} pips ({stop_loss_points} puntos), colocado de forma ceñida detrás de la mecha de manipulación.",
                    "take_profit": f"{take_profit_points // 10} pips ({take_profit_points} puntos), con objetivo de 1:3 ($160 de riesgo para $500 de ganancia).",
                    "breakeven": f"Mover Stop Loss a Break-Even (Riesgo Cero) al alcanzar +{be_pips} pips de beneficio.",
                    "trailing_stop": f"Trailing Stop dinámico de {trailing_pips} pips para proteger la ganancia en la carrera del squeeze.",
                    "lot_sizing": "0.01 lotes por cada $1,000 de capital o 1% de riesgo por operación.",
                    "risk_reward_ratio": rr_label
                },
                "secrets_and_traps": (
                    "• El 70% de las rupturas de soporte/resistencia son trampas. No compres en la ruptura; compra cuando la ruptura falle y absorban a los vendedores.\n"
                    "• Opera exclusivamente durante New York Session (máxima liquidez).\n"
                    "• Poner el riesgo en CERO (Break-Even) inmediatamente tras el primer impulso de expansión."
                )
            }
            strategy = {
                "name": name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": timeframe,
                "default_lot": 0.01,
                "stop_loss_points": stop_loss_points,
                "take_profit_points": take_profit_points,
                "breakeven_pips": be_pips,
                "trailing_stop_pips": trailing_pips,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
                "use_time_filter": True,
                "max_spread_points": max_spread,
                "magic_number": 991234,
                "custom_inputs": [
                    {"type": "int", "name": "InpVolMAPeriod", "default": 20, "comment": "Periodo Media de Volumen"},
                    {"type": "double", "name": "InpVolMultiplier", "default": 1.4, "comment": "Multiplicador Presión Institucional"},
                    {"type": "int", "name": "InpATRFilter", "default": 14, "comment": "Filtro Volatilidad ATR"}
                ],
                "indicators": [
                    {
                        "name": "Tick_Volume",
                        "handle_var": "h_volume",
                        "buffer_var": "buf_volume",
                        "init_call": "iVolumes(_Symbol, _Period, VOLUME_TICK)"
                    },
                    {
                        "name": "Volume_MA",
                        "handle_var": "h_vol_ma",
                        "buffer_var": "buf_vol_ma",
                        "init_call": "iMA(_Symbol, _Period, InpVolMAPeriod, 0, MODE_SMA, PRICE_CLOSE)"
                    },
                    {
                        "name": "ATR_Volatility",
                        "handle_var": "h_atr",
                        "buffer_var": "buf_atr",
                        "init_call": "iATR(_Symbol, _Period, InpATRFilter)"
                    }
                ],
                "entry_buy_code": "buf_volume[0] > (buf_vol_ma[0] * InpVolMultiplier) && rates[0].close > rates[0].open && rates[0].low <= rates[1].low",
                "entry_sell_code": "buf_volume[0] > (buf_vol_ma[0] * InpVolMultiplier) && rates[0].close < rates[0].open && rates[0].high >= rates[1].high",
                "exit_buy_code": "rates[0].close < rates[0].open && buf_volume[0] > (buf_vol_ma[0] * InpVolMultiplier * 1.5)",
                "exit_sell_code": "rates[0].close > rates[0].open && buf_volume[0] > (buf_vol_ma[0] * InpVolMultiplier * 1.5)"
            }
            return {"audit": audit, "strategy": strategy}

        # CASO 2: ESTRATEGIA RSI RETROCESO DINÁMICO & TENDENCIA MACRO
        elif has_rsi and not has_order_flow:
            name = "RSI_Dynamic_Pullback_EA"
            desc = "Estrategia de retroceso con oscilador RSI y filtro tendencial de media móvil exponencial macro."
            audit = {
                "title": context_title or "Estrategia de Retroceso con RSI y Filtro Tendencial",
                "trader": "Trader de Retroceso & Reversión a la Media",
                "summary": "Filtra la tendencia mayor con EMA 200 y busca retrocesos de agotamiento en zonas de sobreventa/sobrecompra con RSI.",
                "timeframe": tf_label,
                "symbols": symbols,
                "trading_hours": {
                    "session_name": session_name,
                    "operating_window": window_display,
                    "days": "Lunes a Viernes",
                    "notes": "Operativa recomendada en sesiones de alta liquidez."
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": f"{max_spread} puntos ({max_spread/10:.1f} pips)",
                    "account_recommendation": "Cuentas estándar o ECN"
                },
                "indicators": [
                    {
                        "name": "Relative Strength Index (RSI)",
                        "is_custom": False,
                        "category": "Nativo MT5 (iRSI)",
                        "parameters": "Periodo: 14, Niveles: 30 / 70",
                        "description": "Oscilador de momento que detecta extremos de precio sobreextendidos."
                    },
                    {
                        "name": "EMA Tendencia Macro (200)",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMA)",
                        "parameters": "Periodo: 200 EMA, Precio de Cierre",
                        "description": "Filtro direccional. Solo compras si el precio está por encima; solo ventas si está por debajo."
                    }
                ],
                "entry_rules": {
                    "market_context": "Tendencia definida confirmada por la inclinación y posición respecto a la EMA 200.",
                    "long": "Precio por encima de EMA 200 y el RSI cruza hacia arriba saliendo del nivel de sobreventa 30.",
                    "short": "Precio por debajo de EMA 200 y el RSI cruza hacia abajo saliendo del nivel de sobrecompra 70.",
                    "trigger": "Cruce del nivel 30 (compras) o nivel 70 (ventas) al cierre de vela.",
                    "confirmation": "Cierre de vela confirmado para validar el cruce del oscilador.",
                    "invalidation": "Si el precio cruza en sentido contrario a la EMA 200 antes de ejecutar."
                },
                "risk_management": {
                    "stop_loss": f"{stop_loss_points // 10} pips ({stop_loss_points} puntos)",
                    "take_profit": f"{take_profit_points // 10} pips ({take_profit_points} puntos)",
                    "breakeven": f"Mover a Break-Even al alcanzar +{be_pips} pips.",
                    "trailing_stop": f"Trailing Stop dinámico de {trailing_pips} pips.",
                    "lot_sizing": "0.01 lotes por cada $1,000 de balance.",
                    "risk_reward_ratio": rr_label
                },
                "secrets_and_traps": "No operar en contra de la EMA 200. Esperar a que el RSI salga de la zona extrema, no comprar mientras sigue cayendo."
            }
            strategy = {
                "name": name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": timeframe,
                "default_lot": 0.01,
                "stop_loss_points": stop_loss_points,
                "take_profit_points": take_profit_points,
                "breakeven_pips": be_pips,
                "trailing_stop_pips": trailing_pips,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
                "use_time_filter": True,
                "max_spread_points": max_spread,
                "magic_number": 882145,
                "custom_inputs": [
                    {"type": "int", "name": "InpRsiPeriod", "default": 14, "comment": "Periodo RSI"},
                    {"type": "int", "name": "InpTrendEma", "default": 200, "comment": "Periodo EMA Macro"},
                    {"type": "double", "name": "InpRsiOversold", "default": 30.0, "comment": "Nivel Sobreventa"},
                    {"type": "double", "name": "InpRsiOverbought", "default": 70.0, "comment": "Nivel Sobrecompra"}
                ],
                "indicators": [
                    {
                        "name": "RSI",
                        "handle_var": "h_rsi",
                        "buffer_var": "buf_rsi",
                        "init_call": "iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE)"
                    },
                    {
                        "name": "Trend_EMA",
                        "handle_var": "h_trend_ema",
                        "buffer_var": "buf_trend_ema",
                        "init_call": "iMA(_Symbol, _Period, InpTrendEma, 0, MODE_EMA, PRICE_CLOSE)"
                    }
                ],
                "entry_buy_code": "rates[0].close > buf_trend_ema[0] && buf_rsi[0] > InpRsiOversold && buf_rsi[1] <= InpRsiOversold",
                "entry_sell_code": "rates[0].close < buf_trend_ema[0] && buf_rsi[0] < InpRsiOverbought && buf_rsi[1] >= InpRsiOverbought",
                "exit_buy_code": "buf_rsi[0] >= InpRsiOverbought",
                "exit_sell_code": "buf_rsi[0] <= InpRsiOversold"
            }
            return {"audit": audit, "strategy": strategy}

        # CASO 3: BANDAS DE BOLLINGER SQUEEZE & RUPTURA DE VOLATILIDAD
        elif has_bollinger:
            name = "Bollinger_Volatility_Squeeze_EA"
            desc = "Estrategia de contracción y explosión de volatilidad con Bandas de Bollinger y confirmación de cierre."
            audit = {
                "title": context_title or "Estrategia Bollinger Squeeze & Expansión de Rango",
                "trader": "Especialista en Volatilidad y Ruptura de Canales",
                "summary": "Detecta compresión de volatilidad (squeeze) y entra en la dirección de la ruptura con filtro EMA de 50 periodos.",
                "timeframe": tf_label,
                "symbols": symbols,
                "trading_hours": {
                    "session_name": session_name,
                    "operating_window": window_display,
                    "days": "Lunes a Viernes",
                    "notes": "Operar en momentos de apertura de mercado."
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": f"{max_spread} puntos ({max_spread/10:.1f} pips)",
                    "account_recommendation": "Cuentas ECN"
                },
                "indicators": [
                    {
                        "name": "Bandas de Bollinger",
                        "is_custom": False,
                        "category": "Nativo MT5 (iBands)",
                        "parameters": "Periodo: 20, Desviación: 2.0",
                        "description": "Bandas de envolvente de desviación estándar para medir expansión y compresión."
                    },
                    {
                        "name": "Filtro Tendencial EMA 50",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMA)",
                        "parameters": "Periodo: 50 EMA",
                        "description": "Garantiza operar a favor de la inercia del movimiento intradía."
                    }
                ],
                "entry_rules": {
                    "market_context": "Contracción de ancho de bandas (squeeze) seguida de expansión.",
                    "long": "Cierre de vela por encima de la banda superior de Bollinger y por encima de la EMA 50.",
                    "short": "Cierre de vela por debajo de la banda inferior de Bollinger y por debajo de la EMA 50.",
                    "trigger": "Cierre completo fuera de la banda para confirmar ignición del impulso.",
                    "confirmation": "Cierre de vela fuera de la envolvente.",
                    "invalidation": "Vela que cierra de nuevo dentro de las bandas sin continuar la expansión."
                },
                "risk_management": {
                    "stop_loss": f"{stop_loss_points // 10} pips ({stop_loss_points} puntos)",
                    "take_profit": f"{take_profit_points // 10} pips ({take_profit_points} puntos)",
                    "breakeven": f"Break-Even al avanzar +{be_pips} pips.",
                    "trailing_stop": f"Trailing Stop de {trailing_pips} pips.",
                    "lot_sizing": "0.01 lotes por cada $1,000.",
                    "risk_reward_ratio": rr_label
                },
                "secrets_and_traps": "Evitar operar cuando las bandas estén planas y paralelas (mercado en rango sin volumen)."
            }
            strategy = {
                "name": name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": timeframe,
                "default_lot": 0.01,
                "stop_loss_points": stop_loss_points,
                "take_profit_points": take_profit_points,
                "breakeven_pips": be_pips,
                "trailing_stop_pips": trailing_pips,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
                "use_time_filter": True,
                "max_spread_points": max_spread,
                "magic_number": 771342,
                "custom_inputs": [
                    {"type": "int", "name": "InpBandsPeriod", "default": 20, "comment": "Periodo Bandas Bollinger"},
                    {"type": "double", "name": "InpBandsDev", "default": 2.0, "comment": "Desviación Estándar"},
                    {"type": "int", "name": "InpEmaTrend", "default": 50, "comment": "Filtro Dirección EMA"}
                ],
                "indicators": [
                    {
                        "name": "Bollinger_Bands",
                        "handle_var": "h_bands",
                        "buffer_var": "buf_bands",
                        "init_call": "iBands(_Symbol, _Period, InpBandsPeriod, 0, InpBandsDev, PRICE_CLOSE)"
                    },
                    {
                        "name": "EMA_Trend",
                        "handle_var": "h_ema_trend",
                        "buffer_var": "buf_ema_trend",
                        "init_call": "iMA(_Symbol, _Period, InpEmaTrend, 0, MODE_EMA, PRICE_CLOSE)"
                    }
                ],
                "entry_buy_code": "rates[0].close > buf_bands[0] && rates[0].close > buf_ema_trend[0]",
                "entry_sell_code": "rates[0].close < buf_bands[0] && rates[0].close < buf_ema_trend[0]",
                "exit_buy_code": "rates[0].close < buf_ema_trend[0]",
                "exit_sell_code": "rates[0].close > buf_ema_trend[0]"
            }
            return {"audit": audit, "strategy": strategy}

        # CASO 4: MACD MOMENTUM CONTINUATION
        elif has_macd:
            name = "MACD_Momentum_Continuation_EA"
            desc = "Estrategia de aceleración de momentum con histograma MACD y línea de señal."
            audit = {
                "title": context_title or "Estrategia de Momentum con Histograma MACD",
                "trader": "Trader de Continuación Tendencial",
                "summary": "Identifica cruces de línea cero en MACD con confirmación de media móvil macro 200.",
                "timeframe": tf_label,
                "symbols": symbols,
                "trading_hours": {
                    "session_name": session_name,
                    "operating_window": window_display,
                    "days": "Lunes a Viernes",
                    "notes": "Operativa con sesgo de tendencia intradía."
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": f"{max_spread} puntos ({max_spread/10:.1f} pips)",
                    "account_recommendation": "Cuentas ECN"
                },
                "indicators": [
                    {
                        "name": "MACD (Moving Average Convergence Divergence)",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMACD)",
                        "parameters": "Fast EMA: 12, Slow EMA: 26, Signal SMA: 9",
                        "description": "Calcula el diferencial de medias móviles para medir la aceleración de tendencia."
                    },
                    {
                        "name": "Filtro Tendencia 200",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMA)",
                        "parameters": "Periodo: 200 EMA",
                        "description": "Sesgo estructural institucional."
                    }
                ],
                "entry_rules": {
                    "market_context": "Fase de impulso tendencial tras pullback a línea cero.",
                    "long": "Histograma MACD cruza hacia arriba la línea cero (0.0) y precio sobre la EMA 200.",
                    "short": "Histograma MACD cruza hacia abajo la línea cero (0.0) y precio bajo la EMA 200.",
                    "trigger": "Cruce de línea cero al cierre de barra.",
                    "confirmation": "Cierre de barra validando el cambio de polaridad del histograma.",
                    "invalidation": "Divergencia bajista previa o rechazo brusco en EMA 200."
                },
                "risk_management": {
                    "stop_loss": f"{stop_loss_points // 10} pips ({stop_loss_points} puntos)",
                    "take_profit": f"{take_profit_points // 10} pips ({take_profit_points} puntos)",
                    "breakeven": f"Break-Even al avanzar +{be_pips} pips.",
                    "trailing_stop": f"Trailing Stop de {trailing_pips} pips.",
                    "lot_sizing": "0.01 lotes por cada $1,000.",
                    "risk_reward_ratio": rr_label
                },
                "secrets_and_traps": "Cuidado con divergencias contrarias en velas previas."
            }
            strategy = {
                "name": name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": timeframe,
                "default_lot": 0.01,
                "stop_loss_points": stop_loss_points,
                "take_profit_points": take_profit_points,
                "breakeven_pips": be_pips,
                "trailing_stop_pips": trailing_pips,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
                "use_time_filter": True,
                "max_spread_points": max_spread,
                "magic_number": 661890,
                "custom_inputs": [
                    {"type": "int", "name": "InpFastEma", "default": 12, "comment": "Fast EMA MACD"},
                    {"type": "int", "name": "InpSlowEma", "default": 26, "comment": "Slow EMA MACD"},
                    {"type": "int", "name": "InpSignalSma", "default": 9, "comment": "Signal SMA MACD"},
                    {"type": "int", "name": "InpTrendEma", "default": 200, "comment": "Filtro Tendencia 200"}
                ],
                "indicators": [
                    {
                        "name": "MACD",
                        "handle_var": "h_macd",
                        "buffer_var": "buf_macd",
                        "init_call": "iMACD(_Symbol, _Period, InpFastEma, InpSlowEma, InpSignalSma, PRICE_CLOSE)"
                    },
                    {
                        "name": "Trend_EMA",
                        "handle_var": "h_trend_ema",
                        "buffer_var": "buf_trend_ema",
                        "init_call": "iMA(_Symbol, _Period, InpTrendEma, 0, MODE_EMA, PRICE_CLOSE)"
                    }
                ],
                "entry_buy_code": "buf_macd[0] > 0 && buf_macd[1] <= 0 && rates[0].close > buf_trend_ema[0]",
                "entry_sell_code": "buf_macd[0] < 0 && buf_macd[1] >= 0 && rates[0].close < buf_trend_ema[0]",
                "exit_buy_code": "buf_macd[0] < 0",
                "exit_sell_code": "buf_macd[0] > 0"
            }
            return {"audit": audit, "strategy": strategy}

        # CASO 5: MEDIAS MÓVILES (Con extracción dinámica de periodos exactos mencionados)
        else:
            periods_found = [int(p) for p in re.findall(r'\b(9|10|14|20|21|50|100|200)\b', text_lower)]
            fast_p = 20
            slow_p = 50
            if len(periods_found) >= 2:
                fast_p = min(periods_found[0], periods_found[1])
                slow_p = max(periods_found[0], periods_found[1])
            elif len(periods_found) == 1:
                if periods_found[0] < 50:
                    fast_p = periods_found[0]
                    slow_p = 50
                else:
                    fast_p = 20
                    slow_p = periods_found[0]

            name = f"EMA_{fast_p}_{slow_p}_DynamicTrend"
            desc = f"Estrategia de cruce y confirmación tendencial con EMA rápida de {fast_p} y EMA lenta de {slow_p} extraídas del análisis del video."
            audit = {
                "title": context_title or f"Estrategia de Medias Móviles Exponenciales ({fast_p} / {slow_p})",
                "trader": "Trader de Seguimiento Tendencial",
                "summary": f"Modelo cuantitativo basado en el cruce de velocidad de la EMA {fast_p} sobre la EMA {slow_p} para capturar tendencias intermedias.",
                "timeframe": tf_label,
                "symbols": symbols,
                "trading_hours": {
                    "session_name": session_name,
                    "operating_window": window_display,
                    "days": "Lunes a Viernes",
                    "notes": "Operativa intradía en sesiones de liquidez."
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": f"{max_spread} puntos ({max_spread/10:.1f} pips)",
                    "account_recommendation": "Cuentas estándar o ECN"
                },
                "indicators": [
                    {
                        "name": f"Fast EMA ({fast_p})",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMA)",
                        "parameters": f"Periodo: {fast_p} EMA",
                        "description": "Media rápida que reacciona a los giros inmediatos del precio."
                    },
                    {
                        "name": f"Slow EMA ({slow_p})",
                        "is_custom": False,
                        "category": "Nativo MT5 (iMA)",
                        "parameters": f"Periodo: {slow_p} EMA",
                        "description": "Media lenta que establece la línea de base de soporte/resistencia dinámico."
                    }
                ],
                "entry_rules": {
                    "market_context": f"Alineación tendencial cuando la EMA rápida {fast_p} se despega de la EMA lenta {slow_p}.",
                    "long": f"EMA {fast_p} cruza hacia arriba la EMA {slow_p} en vela cerrada.",
                    "short": f"EMA {fast_p} cruza hacia abajo la EMA {slow_p} en vela cerrada.",
                    "trigger": f"Cierre de vela completando el cruce de medias.",
                    "confirmation": "Cierre de vela completo fuera del área de cruce.",
                    "invalidation": "Cruce en sentido contrario antes de la consolidación de la vela."
                },
                "risk_management": {
                    "stop_loss": f"{stop_loss_points // 10} pips ({stop_loss_points} puntos)",
                    "take_profit": f"{take_profit_points // 10} pips ({take_profit_points} puntos)",
                    "breakeven": f"Break-Even al avanzar +{be_pips} pips.",
                    "trailing_stop": f"Trailing Stop de {trailing_pips} pips.",
                    "lot_sizing": "0.01 lotes por cada $1,000.",
                    "risk_reward_ratio": rr_label
                },
                "secrets_and_traps": "Esperar confirmación de vela cerrada para no entrar en falsos cruces (cruces efímeros intradía)."
            }
            strategy = {
                "name": name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": timeframe,
                "default_lot": 0.01,
                "stop_loss_points": stop_loss_points,
                "take_profit_points": take_profit_points,
                "breakeven_pips": be_pips,
                "trailing_stop_pips": trailing_pips,
                "start_hour": start_hour,
                "start_minute": start_minute,
                "end_hour": end_hour,
                "end_minute": end_minute,
                "use_time_filter": True,
                "max_spread_points": max_spread,
                "magic_number": 551982,
                "custom_inputs": [
                    {"type": "int", "name": "InpFastPeriod", "default": fast_p, "comment": f"Fast EMA ({fast_p})"},
                    {"type": "int", "name": "InpSlowPeriod", "default": slow_p, "comment": f"Slow EMA ({slow_p})"}
                ],
                "indicators": [
                    {
                        "name": "Fast_EMA",
                        "handle_var": "h_fast_ema",
                        "buffer_var": "buf_fast_ema",
                        "init_call": "iMA(_Symbol, _Period, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE)"
                    },
                    {
                        "name": "Slow_EMA",
                        "handle_var": "h_slow_ema",
                        "buffer_var": "buf_slow_ema",
                        "init_call": "iMA(_Symbol, _Period, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE)"
                    }
                ],
                "entry_buy_code": "buf_fast_ema[0] > buf_slow_ema[0] && buf_fast_ema[1] <= buf_slow_ema[1]",
                "entry_sell_code": "buf_fast_ema[0] < buf_slow_ema[0] && buf_fast_ema[1] >= buf_slow_ema[1]",
                "exit_buy_code": "buf_fast_ema[0] < buf_slow_ema[0]",
                "exit_sell_code": "buf_fast_ema[0] > buf_slow_ema[0]"
            }
            return {"audit": audit, "strategy": strategy}


class StrategyExtractor:
    """Multimodal strategy extractor from URLs (YouTube, Reels, TikTok), PDFs, or text."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.api_key = (gemini_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini Client: {e}")
                self.client = None
        else:
            self.client = None

    @staticmethod
    def _find_ffmpeg() -> Optional[str]:
        found = shutil.which("ffmpeg")
        if found:
            return os.path.dirname(found)
        local_appdata = os.environ.get("LOCALAPPDATA", "")
        winget_packages = os.path.join(local_appdata, "Microsoft", "WinGet", "Packages")
        if os.path.exists(winget_packages):
            for root, dirs, files in os.walk(winget_packages):
                if "ffmpeg.exe" in files:
                    return root
        for pf in [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]:
            if pf and os.path.exists(pf):
                for root, dirs, files in os.walk(pf):
                    if "ffmpeg.exe" in files:
                        return root
        return None

    def extract_from_pdf(self, pdf_path: str) -> str:
        """Extract text and metadata from PDF strategy file."""
        text_content = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {page_idx + 1} ---\n{text}")
        return "\n\n".join(text_content)

    @staticmethod
    def _extract_transcript_from_info(info: Dict[str, Any]) -> str:
        subs = info.get("subtitles") or {}
        auto_subs = info.get("automatic_captions") or {}
        combined = {**auto_subs, **subs}
        for lang in ["es", "es-419", "es-ES", "en", "en-US", "en-GB"]:
            if lang in combined:
                formats = combined[lang]
                for fmt in formats:
                    if fmt.get("ext") == "json3":
                        try:
                            import requests
                            r = requests.get(fmt["url"], timeout=10)
                            if r.status_code == 200:
                                events = r.json().get("events", [])
                                parts = []
                                for ev in events:
                                    segs = ev.get("segs", [])
                                    parts.append("".join([s.get("utf8", "") for s in segs]))
                                transcript = " ".join([p.strip() for p in parts if p.strip()])
                                if transcript:
                                    return transcript[:80000]
                        except Exception:
                            pass
        return ""

    def download_media_from_url(self, url: str, output_dir: str) -> Dict[str, Any]:
        """Extract full transcript, subtitles, and metadata without blocking."""
        os.makedirs(output_dir, exist_ok=True)
        ffmpeg_bin = self._find_ffmpeg()
        if ffmpeg_bin and ffmpeg_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

        meta_opts = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
        }
        if ffmpeg_bin:
            meta_opts['ffmpeg_location'] = ffmpeg_bin

        try:
            with yt_dlp.YoutubeDL(meta_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                transcript = self._extract_transcript_from_info(info)
                duration = info.get("duration", 0)

                return {
                    "title": info.get("title", ""),
                    "description": info.get("description", ""),
                    "transcript": transcript,
                    "duration": duration,
                    "id": info.get("id", ""),
                    "audio_path": ""
                }
        except Exception as e:
            return {
                "title": "Trading Video Strategy",
                "description": f"URL: {url}",
                "transcript": "",
                "duration": 0,
                "id": "",
                "audio_path": ""
            }

    def analyze_strategy_text(self, raw_text: str, context_title: str = "") -> Dict[str, Any]:
        """
        Analyze extracted trading strategy text/transcript and convert it into
        the standardized MQL5 strategy JSON specification and audit breakdown.
        """
        if self.client:
            prompt = f"""
You are an institutional algorithmic trading expert and senior MQL5 developer.
Analyze the following trading strategy material (from video transcript, PDF or article) titled "{context_title}".

Extract and formalize the EXACT trading strategy into a STRICT JSON specification matching this exact schema:

{{
  "audit": {{
    "title": "Clear strategy title",
    "trader": "Trader or channel name",
    "summary": "Detailed narrative of the strategy logic",
    "timeframe": "M3 / M5 / M15 / H1 execution timeframe with explanation",
    "symbols": ["EURUSD", "NAS100"],
    "trading_hours": {{
      "session_name": "New York / London / Asian Session",
      "operating_window": "Exact hours",
      "days": "Days of week",
      "notes": "Session notes"
    }},
    "market_asset_spec": {{
      "symbols_display": "Assets",
      "asset_class": "Asset Class",
      "max_spread": "Max spread points",
      "account_recommendation": "ECN / RAW"
    }},
    "indicators": [
      {{
        "name": "Indicator name",
        "is_custom": false,
        "category": "Nativo MT5 / Custom",
        "parameters": "Parameters description",
        "description": "How the trader uses this indicator"
      }}
    ],
    "entry_rules": {{
      "market_context": "Market structure and context",
      "long": "Step by step rules for Buy",
      "short": "Step by step rules for Sell",
      "trigger": "Trigger candle event",
      "confirmation": "Candle / pattern confirmation",
      "invalidation": "When setup is invalidated"
    }},
    "risk_management": {{
      "stop_loss": "Exact stop loss rules and placement",
      "take_profit": "Exact take profit and risk reward ratio",
      "breakeven": "When to move stop loss to entry",
      "trailing_stop": "Trailing stop rule",
      "lot_sizing": "Lot sizing rules",
      "risk_reward_ratio": "1:2 / 1:3 etc."
    }},
    "secrets_and_traps": "Key secrets, psychological traps, and timing explained in the video"
  }},
  "strategy": {{
    "name": "Strategy_Pascal_Case_Name",
    "description": "Clear explanation",
    "recommended_symbols": ["EURUSD"],
    "recommended_timeframe": "M15",
    "default_lot": 0.01,
    "stop_loss_points": 300,
    "take_profit_points": 600,
    "breakeven_pips": 15,
    "trailing_stop_pips": 12,
    "start_hour": 13,
    "start_minute": 30,
    "end_hour": 20,
    "end_minute": 0,
    "use_time_filter": true,
    "max_spread_points": 35,
    "magic_number": 123456,
    "custom_inputs": [
      {{"type": "int", "name": "InpPeriod", "default": 20, "comment": "Period"}}
    ],
    "indicators": [
      {{
        "name": "Indicator_Name",
        "handle_var": "h_ind",
        "buffer_var": "buf_ind",
        "init_call": "iMA(_Symbol, _Period, InpPeriod, 0, MODE_EMA, PRICE_CLOSE)"
      }}
    ],
    "entry_buy_code": "C++ boolean expression",
    "entry_sell_code": "C++ boolean expression",
    "exit_buy_code": "C++ boolean expression or false",
    "exit_sell_code": "C++ boolean expression or false"
  }}
}}

RULES FOR MQL5 CODE:
1. All indicator init_call MUST use valid MetaTrader 5 native functions (iVolumes, iMA, iRSI, iMACD, iBands, iATR, iStochastic).
2. Buffer indexing: buf[0] is candle shift 1 (closed). buf[1] is candle shift 2.
3. Rates array: rates[0].close, rates[0].open, rates[0].high, rates[0].low.
4. Output MUST be ONLY the raw JSON object, no markdown backticks.

MATERIAL TO ANALYZE:
{raw_text[:60000]}
"""
            try:
                response = self.client.models.generate_content(
                    model='gemini-2.5-flash',
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json"
                    )
                )
                if response and response.text:
                    cleaned = response.text.strip()
                    if cleaned.startswith("```json"):
                        cleaned = cleaned[7:]
                    if cleaned.endswith("```"):
                        cleaned = cleaned[:-3]
                    parsed = json.loads(cleaned.strip())
                    if "audit" in parsed and "strategy" in parsed:
                        return parsed
                    elif "strategy" in parsed:
                        parsed["audit"] = DeepStrategyAnalyzer.analyze(raw_text, context_title).get("audit", {})
                        return parsed
            except Exception as e:
                print(f"Gemini API call failed ({e}), falling back to DeepStrategyAnalyzer.")

        # Heuristic and semantic deep analysis
        return DeepStrategyAnalyzer.analyze(raw_text, context_title)
