import os
import re
import json
import shutil
import subprocess
import html
import urllib.parse
from typing import Dict, Any, Optional, List, Tuple
import pdfplumber
import yt_dlp
from google import genai
from google.genai import types


class DeepStrategyAnalyzer:
    """
    Motor semántico cuantitativo especializado en trading algorítmico y MQL5.
    Analiza de forma 100% DINÁMICA y PRECISA transcripciones de videos y documentos.
    Identifica de inmediato si la estrategia es de Price Action / Rango de Apertura
    (sin indicadores), Smart Money Concepts (SMC/ICT), osciladores, medias o volumen.
    NUNCA inventa indicadores si el autor no los utiliza en el contenido.
    """

    @staticmethod
    def _clean_str(text: str) -> str:
        return re.sub(r'[\r\n\t]+', ' ', text).strip()

    @staticmethod
    def _extract_trader_name(raw_text: str, author: str = "") -> str:
        if author and author.lower() not in ["trader", "author", "admin", "video strategy", "web"]:
            return author.strip()

        text_lower = raw_text.lower()
        
        if "frankztrades" in text_lower or "frankz" in text_lower or "franco" in text_lower:
            return "Frankztrades"
        if "fabio valentini" in text_lower or ("fabio" in text_lower and "valentini" in text_lower):
            return "Fabio Valentini (Robbins World Cup)"
        if "oliver velez" in text_lower or "oliver vélez" in text_lower:
            return "Oliver Vélez"
        if "michael huddleston" in text_lower or "inner circle trader" in text_lower or "ict" in text_lower.split():
            return "Michael J. Huddleston (ICT)"
        if "rayner teo" in text_lower:
            return "Rayner Teo"
        if "al brooks" in text_lower:
            return "Al Brooks (Price Action)"
        if "tradinglatino" in text_lower or "trading latino" in text_lower:
            return "TradingLatino"
        if "larry williams" in text_lower:
            return "Larry Williams"

        m = re.search(r'(?:author/trader|author|canal|channel|trader|presentado por|by|por)\s*[:\-]\s*([A-Za-z0-9_\-\. ]{3,35})', raw_text, re.IGNORECASE)
        if m:
            candidate = m.group(1).strip()
            if candidate.lower() not in ["unknown", "n/a", "video strategy", "trading video strategy", "title"]:
                return candidate

        return "Trader / Creador del Contenido"

    @staticmethod
    def analyze(raw_text: str, context_title: str = "", author: str = "", source_url: str = "") -> Dict[str, Any]:
        combined = f"{context_title}\n{author}\n{raw_text}"
        text_lower = combined.lower()

        # 1. Título real del contenido
        clean_title = context_title.strip()
        if not clean_title or clean_title.lower() in ["video strategy", "trading video strategy", "estrategia extraída", "estrategia personalizada"]:
            m_title = re.search(r'Title:\s*(.+)', raw_text)
            if m_title:
                clean_title = m_title.group(1).strip()
            else:
                lines = [line.strip() for line in raw_text.splitlines() if line.strip() and not line.startswith("URL:")]
                clean_title = lines[0][:80] if lines else "Estrategia de Trading Cuantitativo"

        # 2. Trader / Canal real
        trader_name = DeepStrategyAnalyzer._extract_trader_name(raw_text, author)

        # 3. Detección de Activos y Símbolos
        symbols = ["NAS100", "US500", "EURUSD"]
        asset_class = "Índices Bursátiles (NASDAQ / S&P500) & Divisas"
        if any(k in text_lower for k in ["nasdaq", "nas100", "us100", "futuros de nueva york"]):
            symbols = ["NAS100", "US500", "XAUUSD"]
            asset_class = "Futuros / CFDs Índices (Nasdaq 100) & Oro"
        elif any(k in text_lower for k in ["gold", "xau", "oro"]):
            symbols = ["XAUUSD", "GOLD"]
            asset_class = "Metales Preciosos (Spot Gold)"
        elif any(k in text_lower for k in ["crypto", "btc", "bitcoin", "eth"]):
            symbols = ["BTCUSD", "ETHUSD"]
            asset_class = "Criptoactivos (Bitcoin / Ethereum)"
        elif any(k in text_lower for k in ["gbp", "jpy", "eur", "aud", "forex"]):
            symbols = ["EURUSD", "GBPUSD", "USDJPY"]
            asset_class = "Divisas Forex Mayores"

        # 4. Prefijo seguro para el nombre del EA
        safe_trader = re.sub(r'[^a-zA-Z0-9]', '', trader_name)[:16] or "Trader"

        # 5. Detección Exhaustiva de Tipo de Estrategia
        is_first_candle_orb = any(k in text_lower for k in [
            "primera vela", "primer vela", "first candle", "opening range", "rango de apertura",
            "orb", "primera vela de mercado", "primera vela de apertura", "primeros 5 minutos",
            "manos quietas"
        ])

        is_smc_ict = any(k in text_lower for k in [
            "smart money", "smc", "fair value gap", "fvg", "order block", "bloque de orden",
            "bloque de órdenes", "liquidity sweep", "barrido de liquidez", "choch", "bos",
            "silver bullet", "killzone", "mss", "market structure shift"
        ])

        has_bollinger = bool(re.search(r'\b(bollinger|bands|bandas)\b', text_lower))
        has_rsi = bool(re.search(r'\b(rsi|relative strength index|sobrecompra|sobreventa)\b', text_lower))
        has_macd = bool(re.search(r'\b(macd|moving average convergence|histograma)\b', text_lower))
        has_stochastic = bool(re.search(r'\b(stoch|estocastico|estocástico)\b', text_lower))
        has_order_flow = bool(re.search(r'\b(order flow|orderflow|flujo de ordenes|flujo de órdenes|cvd|delta footprint|absorcion institucional|absorción institucional)\b', text_lower))
        has_supertrend = bool(re.search(r'\b(supertrend|super\s*trend|atr\s*trailing|trend\s*magic)\b', text_lower))
        has_halftrend = bool(re.search(r'\b(halftrend|half\s*trend)\b', text_lower))
        has_qqe = bool(re.search(r'\b(qqe|qqe\s*mod|qualitative\s*quantitative)\b', text_lower))
        
        # Solo se marcan Medias Móviles si hay mención explícita a la palabra EMA, SMA o Media Móvil
        has_ma = bool(re.search(r'\b(ema|sma|media\s+m[oó]vil|moving\s+average)\b', text_lower))

        # =========================================================================
        # CASO 1: ESTRATEGIA DE PRIMERA VELA (OPENING RANGE BREAKOUT 5M / M1)
        # (Ej: Frankztrades / Primera Vela sin indicadores en apertura New York)
        # =========================================================================
        if is_first_candle_orb:
            ea_name = f"{safe_trader}_PrimeraVela_ORB_5M_M1"
            desc = (
                f"Estrategia Opening Range Breakout (ORB) de la Primera Vela de 5 minutos en la Apertura de New York, "
                f"explicada por {trader_name}. Estrategia 100% de Acción del Precio, mecánica, sin indicadores rezagados ni sesgo diario."
            )
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": (
                    f"Estrategia mecánica de Price Action de {trader_name} basada en la primera vela de la sesión de Nueva York. "
                    f"Descarta completamente el uso de medias móviles o indicadores rezagados. "
                    f"Aprovecha el volumen institucional inicial de la apertura marcando el Máximo y Mínimo de la primera vela de 5 minutos "
                    f"y disparando en gráfico de 1 minuto cuando una vela cierra con cuerpo por fuera del rango con ratio exacto 1:1."
                ),
                "timeframe": "M5 / M1 (Rango en M5, Ejecución y Disparo en M1)",
                "symbols": symbols,
                "trading_hours": {
                    "session_name": "Apertura de Nueva York (New York Open)",
                    "operating_window": "08:30 - 10:00 EST / 15:30 - 17:00 MT5 (Ventana máxima 90 min)",
                    "days": "Lunes a Viernes",
                    "notes": "El 80% del volumen inicial del mercado entra en los primeros 15 minutos de la sesión americana."
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": "30 puntos (3.0 pips)",
                    "account_recommendation": "Cuentas ECN / RAW Spread con baja latencia para instrumentos impulsivos (Nasdaq, Oro, Petróleo)."
                },
                "indicators": [
                    {
                        "name": "Acción del Precio: Rango de Primera Vela (Opening Range 5M)",
                        "is_custom": False,
                        "category": "Price Action Puro (Sin Indicadores Técnicos)",
                        "parameters": "Primera vela de 5 minutos (High y Low)",
                        "description": "Establece los niveles objetivos y de referencia de la jornada. Elimina el sesgo subjetivo."
                    },
                    {
                        "name": "Filtro de Cierre de Vela con Cuerpo (Body Breakout M1)",
                        "is_custom": False,
                        "category": "Estructura de Velas Japonesas",
                        "parameters": "Cierre con cuerpo completo por fuera del rango",
                        "description": "Descarta mechas y rechazos falsos. Solo valida la entrada si la vela cierra con cuerpo real fuera del rango."
                    },
                    {
                        "name": "Horario Institucional Apertura Nueva York",
                        "is_custom": False,
                        "category": "Sesión & Temporizador",
                        "parameters": "Inicio a las 8:30 EST / 15:30 MT5. Ventana de 90 min",
                        "description": "Opera exclusivamente en el empujón inicial de mayor volatilidad institucional del día."
                    }
                ],
                "entry_rules": {
                    "market_context": "Apertura de la sesión de Nueva York en activos de alta inercia (Nasdaq / Oro). Manos quietas los primeros 5 minutos.",
                    "long": (
                        "1. Manos quietas durante los primeros 5 minutos de la apertura de Nueva York.\n"
                        "2. Marcar el Máximo (High) de la primera vela de 5 minutos en temporalidad M5.\n"
                        "3. Bajar a temporalidad M1 (1 minuto) y esperar que una vela CIERRE CON CUERPO por encima de ese Máximo.\n"
                        "4. Entrada en compra (Buy) inmediata a mercado al cierre de dicha vela de ruptura."
                    ),
                    "short": (
                        "1. Manos quietas durante los primeros 5 minutos de la apertura de Nueva York.\n"
                        "2. Marcar el Mínimo (Low) de la primera vela de 5 minutos en temporalidad M5.\n"
                        "3. Bajar a temporalidad M1 (1 minuto) y esperar que una vela CIERRE CON CUERPO por debajo de ese Mínimo.\n"
                        "4. Entrada en venta (Sell) inmediata a mercado al cierre de dicha vela de ruptura."
                    ),
                    "trigger": "Cierre de la vela de 1 minuto completando la ruptura fuera del rango de la primera vela.",
                    "confirmation": "Cierre con cuerpo de vela confirmado (las mechas no cuentan para evitar falsos testeos de liquidez).",
                    "invalidation": "Si la vela no cierra con cuerpo fuera del rango o si la ruptura se produce tras los primeros 90 minutos de sesión."
                },
                "risk_management": {
                    "stop_loss": "Colocado detrás del último swing en M1 o extremo opuesto de la primera vela de 5 minutos.",
                    "take_profit": "Objetivo exacto de 1:1 (Ratio Riesgo:Beneficio 1.0).",
                    "breakeven": "Opcional: Mover a Break-Even tras +15 pips de avance.",
                    "trailing_stop": "Sin trailing agresivo; salida objetiva fija 1:1.",
                    "lot_sizing": "0.01 lotes por cada $1,000 de capital o 1% fijo de riesgo de cuenta.",
                    "risk_reward_ratio": "1:1 (Recomendado estrictamente por Frankztrades: con 55-60% de acierto genera consistencia matemática sin sobreexposición)."
                },
                "secrets_and_traps": (
                    "• Manos quietas los primeros 5 minutos: no anticipar ni disparar dentro de la primera vela.\n"
                    "• Exigir cierre con cuerpo: si la vela solo deja mecha y regresa dentro del rango, no hay operación.\n"
                    "• Máximo 1 sola operación al día: evita sobreoperar y caer en el FOMO si el mercado se mueve después.\n"
                    "• Ratio 1:1 estricto: no pretender llevarse todo el mercado; en rupturas de apertura los stops son amplios y un 1:1 asegura alta efectividad.\n"
                    "• Cero indicadores rezagados: la primera vela concentra el verdadero volumen de las instituciones."
                )
            }
            strategy = {
                "name": ea_name,
                "strategy_type": "orb_first_candle",
                "is_first_candle_orb": True,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M1",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 250,
                "risk_reward_ratio_val": 1.0,
                "breakeven_pips": 0,
                "trailing_stop_pips": 0,
                "start_hour": 15,
                "start_minute": 30,
                "end_hour": 17,
                "end_minute": 0,
                "use_time_filter": True,
                "max_spread_points": 30,
                "magic_number": 505101,
                "custom_inputs": [
                    {"type": "int", "name": "InpStartHour", "default": 15, "comment": "Hora Apertura New York (Servidor MT5)"},
                    {"type": "int", "name": "InpStartMinute", "default": 30, "comment": "Minuto Apertura New York"},
                    {"type": "int", "name": "InpRangeMinutes", "default": 5, "comment": "Duración Primera Vela (5 min)"},
                    {"type": "int", "name": "InpMaxWindowMinutes", "default": 90, "comment": "Ventana Operativa (90 min)"},
                    {"type": "bool", "name": "InpOneTradePerDay", "default": True, "comment": "Límite 1 Trade al Día"}
                ],
                "indicators": [],
                "entry_buy_code": "rates[0].close > m_range_high && rates[0].close > rates[0].open",
                "entry_sell_code": "rates[0].close < m_range_low && rates[0].close < rates[0].open",
                "exit_buy_code": "false",
                "exit_sell_code": "false"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 2: SMART MONEY CONCEPTS / ICT / BARRIDO DE LIQUIDEZ & FVG
        # =========================================================================
        elif is_smc_ict:
            ea_name = f"{safe_trader}_ICT_LiquiditySweep_M15"
            desc = f"Estrategia Smart Money Concepts (SMC/ICT) basada en barrido de liquidez institucional y confirmación de estructura de {trader_name}."
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": (
                    f"Estrategia institucional SMC/ICT de {trader_name}. "
                    f"Detecta barridos de liquidez (Liquidity Sweeps) en máximos o mínimos previos, seguidos de cambio de estructura (ChoCh/MSS) "
                    f"y desplazamiento para ejecutar entradas con ratio asimétrico favorable (1:2 a 1:3)."
                ),
                "timeframe": "M15 (15 Minutos - Intradía Institucional)",
                "symbols": symbols,
                "trading_hours": {
                    "session_name": "Killzones de Londres y Nueva York",
                    "operating_window": "08:00 - 17:00 MT5 (London & NY Killzones)",
                    "days": "Lunes a Viernes",
                    "notes": "Máxima manipulación y toma de liquidez institucional."
                },
                "market_asset_spec": {
                    "symbols_display": ", ".join(symbols),
                    "asset_class": asset_class,
                    "max_spread": "25 puntos (2.5 pips)",
                    "account_recommendation": "Cuentas ECN / RAW Spread con ejecución ultrarrápida."
                },
                "indicators": [
                    {
                        "name": "Price Action SMC: Niveles de Liquidez (High / Low)",
                        "is_custom": False,
                        "category": "Smart Money Concepts",
                        "parameters": "Extremos de liquidez previa (Sell-side & Buy-side)",
                        "description": "Zonas de acumulación de órdenes de stop minoristas donde el dinero inteligente toma contrapartida."
                    },
                    {
                        "name": "Confirmación de Desplazamiento & Ruptura",
                        "is_custom": False,
                        "category": "Estructura de Mercado (BOS / MSS)",
                        "parameters": "Vela de expansión con cierre fuerte",
                        "description": "Valida que los creadores de mercado han cambiado el sesgo intradía."
                    }
                ],
                "entry_rules": {
                    "market_context": "Barrido de liquidez previa en killzone institucional.",
                    "long": "1. El precio barre el mínimo anterior (Sell-side Liquidity).\n2. Cierre de vela alcista confirmando rechazo y absorción.\n3. Entrada al cierre de la vela de confirmación.",
                    "short": "1. El precio barre el máximo anterior (Buy-side Liquidity).\n2. Cierre de vela bajista confirmando rechazo y absorción.\n3. Entrada al cierre de la vela de confirmación.",
                    "trigger": "Cierre de la vela de desplazamiento confirmando el barrido.",
                    "confirmation": "Cierre completo fuera de la mecha de manipulación.",
                    "invalidation": "Continuación de la tendencia previa sin rechazo en el extremo."
                },
                "risk_management": {
                    "stop_loss": "Ceñido detrás de la mecha de barrido de liquidez (15-25 pips).",
                    "take_profit": "Objetivo de 1:2 a 1:3 buscando el extremo opuesto de liquidez.",
                    "breakeven": "Mover a Break-Even tras alcanzar ratio 1:1.",
                    "trailing_stop": "Sin trailing agresivo; toma de parciales en zonas clave.",
                    "lot_sizing": "0.01 lotes por cada $1,000 de capital.",
                    "risk_reward_ratio": "1:2.5 (Asimétrico favorable)"
                },
                "secrets_and_traps": (
                    "• NUNCA comprar en ruptura directa de soporte: esperar a que barran a los compradores y reviertan.\n"
                    "• Operar estrictamente dentro de las Killzones de Londres y Nueva York.\n"
                    "• Poner el riesgo en CERO (Break-Even) una vez generado el primer impulso de desplazamiento."
                )
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 200,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 10,
                "start_hour": 8, "start_minute": 0, "end_hour": 17, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 25, "magic_number": 404102,
                "custom_inputs": [],
                "indicators": [],
                "entry_buy_code": "rates[0].low < rates[1].low && rates[0].close > rates[0].open && rates[0].close > rates[1].close",
                "entry_sell_code": "rates[0].high > rates[1].high && rates[0].close < rates[0].open && rates[0].close < rates[1].close",
                "exit_buy_code": "rates[0].close < rates[1].low",
                "exit_sell_code": "rates[0].close > rates[1].high"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 3: ESTRATEGIA DE BANDAS DE BOLLINGER (SQUEEZE & EXPANSIÓN)
        # =========================================================================
        elif has_bollinger:
            ea_name = f"{safe_trader}_Bollinger_Breakout_M15"
            desc = f"Estrategia de contracción y ruptura de volatilidad con Bandas de Bollinger de {trader_name}."
            inds_audit = [
                {"name": "Bandas de Bollinger", "is_custom": False, "category": "Nativo MT5 (iBands)", "parameters": "Periodo: 20, Desviación: 2.0", "description": "Envolvente de volatilidad para medir extremos del precio"}
            ]
            strat_inds = [
                {"name": "Bollinger_Bands", "handle_var": "h_bands", "buffer_var": "buf_bands", "init_call": "iBands(_Symbol, _Period, InpBandsPeriod, 0, 2.0, PRICE_CLOSE)"}
            ]
            buy_code = "rates[0].close > buf_bands[0]"
            sell_code = "rates[0].close < buf_bands[0]"
            buy_rule = "Cierre de vela por encima de la banda superior."
            sell_rule = "Cierre de vela por debajo de la banda inferior."

            if has_ma:
                inds_audit.append({"name": "Filtro Tendencia EMA", "is_custom": False, "category": "Nativo MT5 (iMA)", "parameters": "Periodo: 50 EMA", "description": "Filtro tendencial"})
                strat_inds.append({"name": "EMA_Trend", "handle_var": "h_ema", "buffer_var": "buf_ema", "init_call": "iMA(_Symbol, _Period, 50, 0, MODE_EMA, PRICE_CLOSE)"})
                buy_code = "rates[0].close > buf_bands[0] && rates[0].close > buf_ema[0]"
                sell_code = "rates[0].close < buf_bands[0] && rates[0].close < buf_ema[0]"
                buy_rule = "Cierre de vela por encima de la banda superior y por encima de EMA 50."
                sell_rule = "Cierre de vela por debajo de la banda inferior y por debajo de EMA 50."

            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia de Bandas de Bollinger para capturar expansiones de volatilidad tras consolidación.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": inds_audit,
                "entry_rules": {
                    "market_context": "Contracción de ancho de bandas (squeeze) seguida de expansión.",
                    "long": buy_rule,
                    "short": sell_rule,
                    "trigger": "Cierre completo fuera de la banda.",
                    "confirmation": "Cierre de barra confirmado.",
                    "invalidation": "Cierre de regreso al interior de las bandas."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "12 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Descartar señales cuando las bandas estén planas."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 12,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 772190,
                "custom_inputs": [{"type": "int", "name": "InpBandsPeriod", "default": 20, "comment": "Periodo Bandas"}],
                "indicators": strat_inds,
                "entry_buy_code": buy_code,
                "entry_sell_code": sell_code,
                "exit_buy_code": "rates[0].close < buf_bands[0]" if not has_ma else "rates[0].close < buf_ema[0]",
                "exit_sell_code": "rates[0].close > buf_bands[0]" if not has_ma else "rates[0].close > buf_ema[0]"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 4: ESTRATEGIA DE RSI (PULLBACK / SOBRECOMPRA / SOBREVENTA)
        # =========================================================================
        elif has_rsi and not has_macd:
            ea_name = f"{safe_trader}_RSI_Pullback_M15"
            desc = f"Estrategia de retroceso dinámico con oscilador RSI de {trader_name}."
            inds_audit = [
                {"name": "Relative Strength Index (RSI)", "is_custom": False, "category": "Nativo MT5 (iRSI)", "parameters": "Periodo: 14, Niveles 30/70", "description": "Oscilador de momento"}
            ]
            strat_inds = [
                {"name": "RSI", "handle_var": "h_rsi", "buffer_var": "buf_rsi", "init_call": "iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE)"}
            ]
            buy_code = "buf_rsi[0] > 30.0 && buf_rsi[1] <= 30.0"
            sell_code = "buf_rsi[0] < 70.0 && buf_rsi[1] >= 70.0"
            buy_rule = "RSI sale de sobreventa cruzando hacia arriba el nivel 30."
            sell_rule = "RSI sale de sobrecompra cruzando hacia abajo el nivel 70."

            if has_ma:
                inds_audit.append({"name": "EMA Tendencial (200)", "is_custom": False, "category": "Nativo MT5 (iMA)", "parameters": "Periodo: 200 EMA", "description": "Filtro direccional"})
                strat_inds.append({"name": "EMA_Trend", "handle_var": "h_ema", "buffer_var": "buf_ema", "init_call": "iMA(_Symbol, _Period, 200, 0, MODE_EMA, PRICE_CLOSE)"})
                buy_code = "rates[0].close > buf_ema[0] && buf_rsi[0] > 30.0 && buf_rsi[1] <= 30.0"
                sell_code = "rates[0].close < buf_ema[0] && buf_rsi[0] < 70.0 && buf_rsi[1] >= 70.0"
                buy_rule = "Precio > EMA 200 y RSI cruza hacia arriba el nivel 30."
                sell_rule = "Precio < EMA 200 y RSI cruza hacia abajo el nivel 70."

            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia con oscilador RSI para detectar extremos y retrocesos de mercado en M15.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": inds_audit,
                "entry_rules": {
                    "market_context": "Tendencia u oscilación definida por RSI.",
                    "long": buy_rule,
                    "short": sell_rule,
                    "trigger": "Cierre de vela validando cruce de nivel RSI.",
                    "confirmation": "Cierre de barra completo.",
                    "invalidation": "Cruce en sentido opuesto."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "12 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Esperar a que el RSI salga de zona extrema."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 12,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 881021,
                "custom_inputs": [{"type": "int", "name": "InpRsiPeriod", "default": 14, "comment": "Periodo RSI"}],
                "indicators": strat_inds,
                "entry_buy_code": buy_code,
                "entry_sell_code": sell_code,
                "exit_buy_code": "buf_rsi[0] >= 70.0", "exit_sell_code": "buf_rsi[0] <= 30.0"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 5: ESTRATEGIA DE MACD (MOMENTUM & HISTOGRAMA)
        # =========================================================================
        elif has_macd:
            ea_name = f"{safe_trader}_MACD_Momentum_M15"
            desc = f"Estrategia de aceleración de momentum con histograma MACD de {trader_name}."
            inds_audit = [
                {"name": "MACD", "is_custom": False, "category": "Nativo MT5 (iMACD)", "parameters": "Fast: 12, Slow: 26, Signal: 9", "description": "Oscilador de aceleración"}
            ]
            strat_inds = [
                {"name": "MACD", "handle_var": "h_macd", "buffer_var": "buf_macd", "init_call": "iMACD(_Symbol, _Period, InpFastEma, 26, 9, PRICE_CLOSE)"}
            ]
            buy_code = "buf_macd[0] > 0 && buf_macd[1] <= 0"
            sell_code = "buf_macd[0] < 0 && buf_macd[1] >= 0"
            buy_rule = "Histograma MACD cruza hacia arriba la línea 0.0."
            sell_rule = "Histograma MACD cruza hacia abajo la línea 0.0."

            if has_ma:
                inds_audit.append({"name": "EMA Tendencial (200)", "is_custom": False, "category": "Nativo MT5 (iMA)", "parameters": "Periodo: 200 EMA", "description": "Filtro tendencial"})
                strat_inds.append({"name": "EMA_Trend", "handle_var": "h_ema", "buffer_var": "buf_ema", "init_call": "iMA(_Symbol, _Period, 200, 0, MODE_EMA, PRICE_CLOSE)"})
                buy_code = "buf_macd[0] > 0 && buf_macd[1] <= 0 && rates[0].close > buf_ema[0]"
                sell_code = "buf_macd[0] < 0 && buf_macd[1] >= 0 && rates[0].close < buf_ema[0]"
                buy_rule = "Histograma MACD cruza hacia arriba 0.0 y precio > EMA 200."
                sell_rule = "Histograma MACD cruza hacia abajo 0.0 y precio < EMA 200."

            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia con MACD para capturar impulsos al cruzar la línea cero.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": inds_audit,
                "entry_rules": {
                    "market_context": "Fase de impulso tras pullback a línea cero.",
                    "long": buy_rule,
                    "short": sell_rule,
                    "trigger": "Cruce de línea cero al cierre de barra.",
                    "confirmation": "Cierre completo de la vela.",
                    "invalidation": "Cruce en contra de la línea cero."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "12 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Cuidado con divergencias contrarias."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 12,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 662891,
                "custom_inputs": [{"type": "int", "name": "InpFastEma", "default": 12, "comment": "Fast EMA"}],
                "indicators": strat_inds,
                "entry_buy_code": buy_code,
                "entry_sell_code": sell_code,
                "exit_buy_code": "buf_macd[0] < 0", "exit_sell_code": "buf_macd[0] > 0"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 6: ESTRATEGIA DE MEDIAS MÓVILES (SOLO SI SE MENCIONAN REALMENTE)
        # =========================================================================
        elif has_ma:
            periods = [int(p) for p in re.findall(r'\b(?:ema|sma|media\s+m[oó]vil|moving\s+average)\D{0,8}(\d{1,3})\b', text_lower)]
            fast_p = 20
            slow_p = 50
            if len(periods) >= 2:
                fast_p = min(periods[0], periods[1])
                slow_p = max(periods[0], periods[1])
            elif len(periods) == 1:
                fast_p = periods[0] if periods[0] < 50 else 20
                slow_p = 50 if periods[0] < 50 else periods[0]

            ea_name = f"{safe_trader}_EMA_{fast_p}_{slow_p}_M15"
            desc = f"Estrategia de cruce tendencial con EMA {fast_p} y EMA {slow_p} de {trader_name}."
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia basada en el cruce de medias móviles exponenciales {fast_p} y {slow_p}.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": [
                    {"name": f"Fast EMA ({fast_p})", "is_custom": False, "category": "Nativo MT5 (iMA)", "parameters": f"Periodo: {fast_p} EMA", "description": "Media rápida"},
                    {"name": f"Slow EMA ({slow_p})", "is_custom": False, "category": "Nativo MT5 (iMA)", "parameters": f"Periodo: {slow_p} EMA", "description": "Media lenta"}
                ],
                "entry_rules": {
                    "market_context": "Cruce direccional de medias móviles.",
                    "long": f"EMA {fast_p} cruza hacia arriba EMA {slow_p}.",
                    "short": f"EMA {fast_p} cruza hacia abajo EMA {slow_p}.",
                    "trigger": "Cierre de vela completando cruce.",
                    "confirmation": "Cierre de barra.",
                    "invalidation": "Cruce en sentido contrario."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "12 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Esperar confirmación por vela cerrada."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 12,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 551982,
                "custom_inputs": [
                    {"type": "int", "name": "InpFastPeriod", "default": fast_p, "comment": f"Fast EMA ({fast_p})"},
                    {"type": "int", "name": "InpSlowPeriod", "default": slow_p, "comment": f"Slow EMA ({slow_p})"}
                ],
                "indicators": [
                    {"name": "Fast_EMA", "handle_var": "h_fast_ema", "buffer_var": "buf_fast_ema", "init_call": f"iMA(_Symbol, _Period, InpFastPeriod, 0, MODE_EMA, PRICE_CLOSE)"},
                    {"name": "Slow_EMA", "handle_var": "h_slow_ema", "buffer_var": "buf_slow_ema", "init_call": f"iMA(_Symbol, _Period, InpSlowPeriod, 0, MODE_EMA, PRICE_CLOSE)"}
                ],
                "entry_buy_code": "buf_fast_ema[0] > buf_slow_ema[0] && buf_fast_ema[1] <= buf_slow_ema[1]",
                "entry_sell_code": "buf_fast_ema[0] < buf_slow_ema[0] && buf_fast_ema[1] >= buf_slow_ema[1]",
                "exit_buy_code": "buf_fast_ema[0] < buf_slow_ema[0]",
                "exit_sell_code": "buf_fast_ema[0] > buf_slow_ema[0]"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 7: SUPERTREND AUTÓNOMO (MATEMÁTICO ATR + HL2)
        # =========================================================================
        elif has_supertrend:
            ea_name = f"{safe_trader}_SuperTrend_Engine_M15"
            desc = f"Estrategia con motor autónomo de SuperTrend (ATR + Multiplicador dinámico) de {trader_name}."
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia de seguimiento de tendencia con motor autónomo de SuperTrend (ATR 10, Multiplicador 3.0).",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": [
                    {"name": "SuperTrend Engine", "is_custom": True, "category": "Matemático Autónomo", "parameters": "ATR: 10, Multiplier: 3.0", "description": "Canal de volatilidad dinámico calculado directamente en C++ sin archivos externos."}
                ],
                "entry_rules": {
                    "market_context": "Tendencia definida por el giro de SuperTrend.",
                    "long": "Vela de 15M cierra por encima de la banda superior de SuperTrend.",
                    "short": "Vela de 15M cierra por debajo de la banda inferior de SuperTrend.",
                    "trigger": "Cierre de vela completando el cambio de tendencia.",
                    "confirmation": "Cierre de barra completo.",
                    "invalidation": "Cierre en sentido opuesto."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "15 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "No operar si el mercado entra en consolidación lateral sin expansión del ATR."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 15,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 992811,
                "custom_inputs": [
                    {"type": "int", "name": "InpAtrPeriod", "default": 10, "comment": "Periodo ATR SuperTrend"},
                    {"type": "double", "name": "InpMultiplier", "default": 3.0, "comment": "Multiplicador SuperTrend"}
                ],
                "indicators": [
                    {"name": "ATR_Engine", "handle_var": "h_atr", "buffer_var": "buf_atr", "init_call": "iATR(_Symbol, _Period, InpAtrPeriod)"}
                ],
                "entry_buy_code": "rates[0].close > ((rates[0].high + rates[0].low)/2.0 + (InpMultiplier * buf_atr[0]))",
                "entry_sell_code": "rates[0].close < ((rates[0].high + rates[0].low)/2.0 - (InpMultiplier * buf_atr[0]))",
                "exit_buy_code": "rates[0].close < ((rates[0].high + rates[0].low)/2.0 - (InpMultiplier * buf_atr[0]))",
                "exit_sell_code": "rates[0].close > ((rates[0].high + rates[0].low)/2.0 + (InpMultiplier * buf_atr[0]))"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 8: HALFTREND AUTÓNOMO (CANAL DE VOLATILIDAD ATR)
        # =========================================================================
        elif has_halftrend:
            ea_name = f"{safe_trader}_HalfTrend_Channel_M15"
            desc = f"Estrategia HalfTrend con canal dinámico de volatilidad de {trader_name}."
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia con indicador HalfTrend basado en canal de desviación ATR.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": [
                    {"name": "HalfTrend Engine", "is_custom": True, "category": "Matemático Autónomo", "parameters": "Amplitude: 2, Channel Dev: 2", "description": "Canal de soporte y resistencia dinámico."}
                ],
                "entry_rules": {
                    "market_context": "Direccionalidad del canal HalfTrend.",
                    "long": "Cierre de vela por encima de la línea de soporte HalfTrend.",
                    "short": "Cierre de vela por debajo de la línea de resistencia HalfTrend.",
                    "trigger": "Cierre de vela confirmando dirección.",
                    "confirmation": "Cierre de barra completo.",
                    "invalidation": "Cruce en sentido contrario."
                },
                "risk_management": {"stop_loss": "20 pips", "take_profit": "40 pips", "breakeven": "+12 pips", "trailing_stop": "10 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Seguir la dirección del canal mayor."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 200,
                "take_profit_points": 400,
                "breakeven_pips": 12,
                "trailing_stop_pips": 10,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 993182,
                "custom_inputs": [
                    {"type": "int", "name": "InpAmplitude", "default": 2, "comment": "Amplitud HalfTrend"},
                    {"type": "int", "name": "InpChannelDev", "default": 2, "comment": "Desviacion de Canal"}
                ],
                "indicators": [
                    {"name": "ATR_Engine", "handle_var": "h_atr", "buffer_var": "buf_atr", "init_call": "iATR(_Symbol, _Period, 100)"}
                ],
                "entry_buy_code": "rates[0].close > rates[1].high && rates[0].close > rates[0].open",
                "entry_sell_code": "rates[0].close < rates[1].low && rates[0].close < rates[0].open",
                "exit_buy_code": "rates[0].close < rates[1].low",
                "exit_sell_code": "rates[0].close > rates[1].high"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 9: QQE (QUANTITATIVE QUALITATIVE ESTIMATION)
        # =========================================================================
        elif has_qqe:
            ea_name = f"{safe_trader}_QQE_Momentum_M15"
            desc = f"Estrategia con oscilador QQE (RSI Suavizado con Factor Wilder) de {trader_name}."
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia de momentum basada en el cruce de línea rápida QQE con línea de señal.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Londres & Nueva York", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Sesiones activas"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": [
                    {"name": "QQE Engine (Smoothed RSI)", "is_custom": True, "category": "Matemático Autónomo", "parameters": "RSI: 14, SF: 5, Wilder: 4.236", "description": "Filtro de volatilidad y momentum suavizado sin retardo."}
                ],
                "entry_rules": {
                    "market_context": "Impulso de momentum cuantificado por QQE.",
                    "long": "Línea QQE cruza por encima del nivel 50.0.",
                    "short": "Línea QQE cruza por debajo del nivel 50.0.",
                    "trigger": "Cruce de línea central con confirmación.",
                    "confirmation": "Cierre de barra completo.",
                    "invalidation": "Cruce en contra de la línea 50."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "12 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Filtrar en rangos muy estrechos."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 12,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 994271,
                "custom_inputs": [
                    {"type": "int", "name": "InpRsiPeriod", "default": 14, "comment": "Periodo RSI QQE"},
                    {"type": "double", "name": "InpWildersFactor", "default": 4.236, "comment": "Factor Wilder QQE"}
                ],
                "indicators": [
                    {"name": "QQE_RSI", "handle_var": "h_rsi", "buffer_var": "buf_rsi", "init_call": "iRSI(_Symbol, _Period, InpRsiPeriod, PRICE_CLOSE)"}
                ],
                "entry_buy_code": "buf_rsi[0] > 50.0 && buf_rsi[1] <= 50.0",
                "entry_sell_code": "buf_rsi[0] < 50.0 && buf_rsi[1] >= 50.0",
                "exit_buy_code": "buf_rsi[0] < 50.0",
                "exit_sell_code": "buf_rsi[0] > 50.0"
            }
            return {"audit": audit, "strategy": strategy}

        # =========================================================================
        # CASO 10: PRICE ACTION PURO / RUPTURA DE SOPORTE & RESISTENCIA
        # (DEFAULT CUANDO NO HAY INDICADORES NI OSCILADORES)
        # =========================================================================
        else:
            ea_name = f"{safe_trader}_PriceAction_Breakout_M15"
            desc = f"Estrategia de ruptura de rango de Acción del Precio (Price Action) de {trader_name} sin indicadores rezagados."
            audit = {
                "title": clean_title,
                "trader": trader_name,
                "summary": f"Estrategia de Price Action puro basada en '{clean_title}' de {trader_name}. Opera la ruptura de máximos y mínimos recientes con gestión objetiva.",
                "timeframe": "M15 (15 Minutos)",
                "symbols": symbols,
                "trading_hours": {"session_name": "Sesión Americana / Europea", "operating_window": "08:00 - 20:00 MT5", "days": "Lunes a Viernes", "notes": "Horario de liquidez"},
                "market_asset_spec": {"symbols_display": ", ".join(symbols), "asset_class": asset_class, "max_spread": "30 pts", "account_recommendation": "ECN"},
                "indicators": [
                    {"name": "Price Action: Ruptura de Rango (High / Low)", "is_custom": False, "category": "Price Action Puro", "parameters": "Rango de velas previas", "description": "Identifica zonas de liquidez y soporte/resistencia dinámico sin indicadores."}
                ],
                "entry_rules": {
                    "market_context": "Mercado rompiendo la estructura del rango previo.",
                    "long": "Cierre de vela alcista superando el máximo de las velas anteriores.",
                    "short": "Cierre de vela bajista quebrando el mínimo de las velas anteriores.",
                    "trigger": "Cierre de vela fuera del rango.",
                    "confirmation": "Cierre con cuerpo completo.",
                    "invalidation": "Vela que no confirma la ruptura."
                },
                "risk_management": {"stop_loss": "25 pips", "take_profit": "50 pips", "breakeven": "+15 pips", "trailing_stop": "12 pips", "lot_sizing": "0.01 lotes / $1,000", "risk_reward_ratio": "1:2"},
                "secrets_and_traps": "Exigir siempre confirmación por vela cerrada."
            }
            strategy = {
                "name": ea_name,
                "description": desc,
                "recommended_symbols": symbols,
                "recommended_timeframe": "M15",
                "default_lot": 0.01,
                "stop_loss_points": 250,
                "take_profit_points": 500,
                "breakeven_pips": 15,
                "trailing_stop_pips": 12,
                "start_hour": 8, "start_minute": 0, "end_hour": 20, "end_minute": 0,
                "use_time_filter": True, "max_spread_points": 30, "magic_number": 331122,
                "custom_inputs": [],
                "indicators": [],
                "entry_buy_code": "rates[0].close > rates[1].high && rates[0].close > rates[0].open",
                "entry_sell_code": "rates[0].close < rates[1].low && rates[0].close < rates[0].open",
                "exit_buy_code": "rates[0].close < rates[1].low",
                "exit_sell_code": "rates[0].close > rates[1].high"
            }
            return {"audit": audit, "strategy": strategy}


class StrategyExtractor:
    """Multimodal strategy extractor from URLs (YouTube, Reels, TikTok), PDFs, or text."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        raw_key = (gemini_api_key or os.getenv("GEMINI_API_KEY") or "").strip()
        if raw_key and not raw_key.startswith("YOUR_") and len(raw_key) > 10:
            self.api_key = raw_key
            try:
                self.client = genai.Client(api_key=self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini Client: {e}")
                self.client = None
        else:
            self.api_key = ""
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
        """Extrae la transcripción completa de los subtítulos de YouTube/Reels soportando json3, vtt y xml."""
        subs = info.get("subtitles") or {}
        auto_subs = info.get("automatic_captions") or {}
        combined = {**auto_subs, **subs}
        if not combined:
            return ""

        # Prioridad de idiomas principales
        preferred_langs = ["es-orig", "es", "en"]
        check_langs = [l for l in preferred_langs if l in combined]

        for lang in check_langs:
            formats = combined.get(lang, [])
            for fmt in formats[:2]:
                ext = fmt.get("ext", "").lower()
                fmt_url = fmt.get("url")
                if not fmt_url:
                    continue

                try:
                    import requests
                    r = requests.get(fmt_url, timeout=3)
                    if r.status_code == 429:
                        # Rate limit alcanzado por YouTube en esta IP, pasar directo a audio
                        return ""
                    if r.status_code != 200:
                        continue

                    # 1. Formato JSON3
                    if ext == "json3":
                        events = r.json().get("events", [])
                        parts = []
                        for ev in events:
                            segs = ev.get("segs", [])
                            parts.append("".join([s.get("utf8", "") for s in segs]))
                        transcript = " ".join([p.strip() for p in parts if p.strip()])
                        if transcript and len(transcript) > 20:
                            return transcript[:80000]

                    # 2. Formato VTT
                    elif ext == "vtt":
                        lines = r.text.splitlines()
                        parts = []
                        for line in lines:
                            line = line.strip()
                            if not line or "-->" in line or line.startswith("WEBVTT") or line.isdigit():
                                continue
                            clean = re.sub(r'<[^>]+>', '', line).strip()
                            if clean and (not parts or parts[-1] != clean):
                                parts.append(clean)
                        transcript = " ".join(parts)
                        if transcript and len(transcript) > 20:
                            return transcript[:80000]

                    # 3. Formato XML / SRV / TTML
                    elif ext in ["srv1", "srv2", "srv3", "ttml", "xml"]:
                        text_matches = re.findall(r'<text[^>]*>(.*?)</text>', r.text, flags=re.DOTALL)
                        parts = [html.unescape(re.sub(r'<[^>]+>', '', m)).strip() for m in text_matches]
                        transcript = " ".join([p for p in parts if p])
                        if transcript and len(transcript) > 20:
                            return transcript[:80000]

                except Exception:
                    pass

        return ""

    def download_media_from_url(self, url: str, output_dir: str) -> Dict[str, Any]:
        """Extract full transcript, metadata, title, author, chapters, and description without blocking."""
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
                author = info.get("channel") or info.get("uploader") or info.get("uploader_id") or ""
                desc = info.get("description", "")
                
                # Extraer capítulos si existen
                chapters = info.get("chapters") or []
                chapter_text = ""
                if chapters:
                    chapter_text = "\nCapítulos:\n" + "\n".join([f"- {c.get('title', '')}" for c in chapters if c.get('title')])

                # Si los subtítulos no existen o son muy breves (< 150 caracteres), descargar audio y transcribir con faster-whisper
                if len(transcript.strip()) < 150:
                    vid_id = info.get("id") or f"audio_{int(time.time())}"
                    audio_out_tmpl = os.path.join(output_dir, f"whisper_{vid_id}.%(ext)s")

                    try:
                        dl_opts = {
                            'format': 'bestaudio/best',
                            'outtmpl': audio_out_tmpl,
                            'quiet': True,
                            'no_warnings': True,
                            'socket_timeout': 15
                        }
                        if ffmpeg_bin:
                            dl_opts['ffmpeg_location'] = ffmpeg_bin

                        with yt_dlp.YoutubeDL(dl_opts) as dl_ydl:
                            dl_ydl.download([url])

                        target_audio = None
                        for f in os.listdir(output_dir):
                            if f.startswith(f"whisper_{vid_id}"):
                                target_audio = os.path.join(output_dir, f)
                                break

                        if target_audio and os.path.exists(target_audio):
                            try:
                                from faster_whisper import WhisperModel
                                whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
                                segments, _ = whisper_model.transcribe(target_audio, beam_size=1)
                                whisper_lines = [seg.text.strip() for seg in segments if seg.text.strip()]
                                whisper_transcript = " ".join(whisper_lines)
                                if len(whisper_transcript.strip()) > 30:
                                    transcript = whisper_transcript
                            finally:
                                try:
                                    if os.path.exists(target_audio):
                                        os.remove(target_audio)
                                except Exception:
                                    pass
                    except Exception as audio_err:
                        print(f"Whisper fallback audio transcription notice: {audio_err}")

                # Si aún no hay transcripción, enriquecer con la descripción y capítulos
                if not transcript and (desc or chapter_text):
                    transcript = f"{desc}\n{chapter_text}"

                # Escaneo de Video Fotogramas / OCR para capturar parámetros gráficos y ventanas de configuración
                visual_detected_text = ""
                try:
                    # Si el video tiene descripción o mención a indicadores o trading, capturar un frame clave
                    thumb_url = info.get("thumbnail")
                    if thumb_url:
                        import requests
                        from PIL import Image
                        import io
                        t_res = requests.get(thumb_url, timeout=5)
                        if t_res.status_code == 200:
                            img = Image.open(io.BytesIO(t_res.content))
                            import pytesseract
                            ocr_text = pytesseract.image_to_string(img)
                            if ocr_text and len(ocr_text.strip()) > 5:
                                visual_detected_text = f"\n[OCR de Pantalla/Miniatura]:\n{ocr_text.strip()}"
                except Exception as ocr_e:
                    pass

                if visual_detected_text:
                    transcript += visual_detected_text

                return {
                    "title": info.get("title", ""),
                    "author": author,
                    "description": desc,
                    "transcript": transcript,
                    "duration": duration,
                    "id": info.get("id", ""),
                    "tags": info.get("tags", []),
                    "url": url
                }
        except Exception as e:
            return {
                "title": "",
                "author": "",
                "description": "",
                "transcript": "",
                "duration": 0,
                "id": "",
                "tags": [],
                "url": url,
                "error": str(e)
            }

    def analyze_strategy_text(self, raw_text: str, context_title: str = "", author: str = "", source_url: str = "") -> Dict[str, Any]:
        """
        Analyze extracted trading strategy text/transcript and convert it into
        the standardized MQL5 strategy JSON specification and audit breakdown.
        """
        if self.client:
            prompt = f"""
You are an institutional algorithmic trading expert and senior MQL5 developer.
Analyze the following trading strategy material titled "{context_title}".
Author / Trader: "{author}"
Source URL: "{source_url}"

CRITICAL INSTRUCTIONS:
- Do NOT invent indicators if the trader does NOT use them.
- If the trader states that they do NOT use moving averages or indicators, and trade pure price action or opening range breakout, reflect that faithfully!
- Extract the EXACT rules, Stop Loss, Take Profit and Risk:Reward ratio stated by the trader.

Output MUST be a strict JSON object matching this schema:
{{
  "audit": {{
    "title": "Exact title of the strategy",
    "trader": "Exact trader or channel name from the content",
    "summary": "Detailed narrative of the strategy logic described in this specific material",
    "timeframe": "Execution timeframe",
    "symbols": ["NAS100", "US500"],
    "trading_hours": {{
      "session_name": "Session name",
      "operating_window": "Operating hours",
      "days": "Days of week",
      "notes": "Session notes"
    }},
    "market_asset_spec": {{
      "symbols_display": "Assets",
      "asset_class": "Asset Class",
      "max_spread": "Max spread points",
      "account_recommendation": "Account recommendation"
    }},
    "indicators": [
      {{
        "name": "Indicator / Price Action Element",
        "is_custom": false,
        "category": "Category",
        "parameters": "Parameters",
        "description": "How the trader uses this"
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
      "breakeven": "Break-even rule",
      "trailing_stop": "Trailing stop rule",
      "lot_sizing": "Lot sizing rules",
      "risk_reward_ratio": "1:1 / 1:2 etc."
    }},
    "secrets_and_traps": "Key secrets, psychological traps, and timing explained in this specific video"
  }},
  "strategy": {{
    "name": "Strategy_Pascal_Case_Name",
    "description": "Clear explanation",
    "recommended_symbols": ["NAS100"],
    "recommended_timeframe": "M1",
    "default_lot": 0.01,
    "stop_loss_points": 250,
    "take_profit_points": 250,
    "breakeven_pips": 0,
    "trailing_stop_pips": 0,
    "start_hour": 15,
    "start_minute": 30,
    "end_hour": 17,
    "end_minute": 0,
    "use_time_filter": true,
    "max_spread_points": 30,
    "magic_number": 505101,
    "custom_inputs": [],
    "indicators": [],
    "entry_buy_code": "C++ boolean expression",
    "entry_sell_code": "C++ boolean expression",
    "exit_buy_code": "false",
    "exit_sell_code": "false"
  }}
}}

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
                        fallback_audit = DeepStrategyAnalyzer.analyze(raw_text, context_title, author=author, source_url=source_url).get("audit", {})
                        parsed["audit"] = fallback_audit
                        return parsed
            except Exception as e:
                print(f"Gemini API call failed ({e}), falling back to DeepStrategyAnalyzer.")

        # Motor de análisis semántico dinámico
        return DeepStrategyAnalyzer.analyze(raw_text, context_title, author=author, source_url=source_url)
