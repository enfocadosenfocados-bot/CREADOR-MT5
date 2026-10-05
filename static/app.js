// State variables
let currentStrategy = null;
let currentAudit = null;
let currentMql5Code = "";
let currentRunId = null;
let equityChart = null;

// Initialize when page loads
document.addEventListener("DOMContentLoaded", () => {
  fetchSystemStatus();
  // Pre-load default search in Radar tab
  executeScraperSearch("profitable trading strategy 2026");
});

// Tab switching
function switchTab(tabId) {
  document.querySelectorAll(".tab-pane").forEach(el => el.classList.add("hidden"));
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.classList.remove("border-emerald-500", "text-emerald-400");
    btn.classList.add("border-transparent", "text-slate-400");
  });

  const targetPane = document.getElementById(tabId);
  const targetBtn = document.getElementById("btn-" + tabId);

  if (targetPane) targetPane.classList.remove("hidden");
  if (targetBtn) {
    targetBtn.classList.remove("border-transparent", "text-slate-400");
    targetBtn.classList.add("border-emerald-500", "text-emerald-400");
  }
}

// Ingestion mode switching
function setIngestMode(mode) {
  const modes = ['url', 'pdf', 'text'];
  modes.forEach(m => {
    const c = document.getElementById(`container-${m}`);
    const b = document.getElementById(`mode-${m}`);
    if (m === mode) {
      c.classList.remove("hidden");
      b.classList.remove("text-slate-400");
      b.classList.add("bg-emerald-600", "text-white");
    } else {
      c.classList.add("hidden");
      b.classList.remove("bg-emerald-600", "text-white");
      b.classList.add("text-slate-400");
    }
  });
}

// Fetch MT5 System and Account Status
async function fetchSystemStatus() {
  try {
    const res = await fetch("/api/system/status");
    const data = await res.json();
    const badgeText = document.getElementById("terminalStatusText");
    const accSummary = document.getElementById("accountSummary");

    if (data.status === "online") {
      badgeText.innerText = "MT5 MCP Conectado";
      const acc = data.account;
      accSummary.innerText = `${acc.login || '53066560'} (${acc.server || 'ICMarkets'}) | $${(acc.balance || 412.76).toFixed(2)} ${acc.currency || 'USD'}`;
      
      // Update MT5 Trade Server Time in top bar
      if (data.time_info && data.time_info.trade_server_last_known_time) {
        const rawTime = data.time_info.trade_server_last_known_time;
        const timePart = rawTime.includes("T") ? rawTime.split("T")[1].substring(0, 5) : rawTime;
        const serverEl = document.getElementById("serverTimeText");
        if (serverEl) {
          serverEl.innerText = `Servidor MT5: ${timePart} (GMT+3)`;
        }
      }
    } else {
      badgeText.innerText = "MT5 MCP Desconectado";
      accSummary.innerText = "Ajusta MCP en Configuración";
    }
  } catch (err) {
    console.warn("Status fetch error:", err);
  }
}

// ==================== CONFIGURATION MODAL ====================

async function openConfigModal() {
  try {
    const res = await fetch("/api/config");
    const cfg = await res.json();
    document.getElementById("cfgTerminalUrl").value = cfg.terminal_url || "http://127.0.0.1:22346/mcp";
    document.getElementById("cfgTerminalToken").value = cfg.terminal_token || "";
    document.getElementById("cfgMetaEditorUrl").value = cfg.metaeditor_url || "http://127.0.0.1:22345/mcp";
    document.getElementById("cfgMetaEditorToken").value = cfg.metaeditor_token || "";
    document.getElementById("cfgMetaEditorExe").value = cfg.metaeditor_exe || "";
    document.getElementById("cfgGeminiKey").value = cfg.gemini_api_key || "";
    document.getElementById("configFeedback").innerText = "";
    document.getElementById("configModal").classList.remove("hidden");
  } catch (e) {
    alert("Error al cargar configuración: " + e.message);
  }
}

function closeConfigModal() {
  document.getElementById("configModal").classList.add("hidden");
}

async function saveConfigModal() {
  const btn = document.getElementById("btnSaveConfig");
  const fb = document.getElementById("configFeedback");
  btn.disabled = true;
  fb.innerText = "Guardando y reconectando...";

  const payload = {
    terminal_url: document.getElementById("cfgTerminalUrl").value.trim(),
    terminal_token: document.getElementById("cfgTerminalToken").value.trim(),
    metaeditor_url: document.getElementById("cfgMetaEditorUrl").value.trim(),
    metaeditor_token: document.getElementById("cfgMetaEditorToken").value.trim(),
    metaeditor_exe: document.getElementById("cfgMetaEditorExe").value.trim(),
    gemini_api_key: document.getElementById("cfgGeminiKey").value.trim()
  };

  try {
    const res = await fetch("/api/config", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.success) {
      fb.innerText = "✅ Configuración guardada y reconectada!";
      setTimeout(() => {
        closeConfigModal();
        fetchSystemStatus();
      }, 1000);
    } else {
      fb.innerText = "❌ Error al guardar";
    }
  } catch (err) {
    fb.innerText = "Error: " + err.message;
  } finally {
    btn.disabled = false;
  }
}

// ==================== RADAR & SCRAPING ENGINE ====================

function searchStrategies(keyword) {
  document.getElementById("scraperQuery").value = keyword;
  executeScraperSearch(keyword);
}

async function executeScraperSearch(customQuery = null) {
  const q = customQuery || document.getElementById("scraperQuery").value.trim() || "profitable trading strategy";
  const cat = document.getElementById("scraperCategory").value;
  const loading = document.getElementById("scraperLoading");
  const grid = document.getElementById("scraperGrid");

  loading.classList.remove("hidden");
  grid.innerHTML = "";

  try {
    const res = await fetch(`/api/scraper/search?q=${encodeURIComponent(q)}&category=${cat}`);
    const data = await res.json();
    loading.classList.add("hidden");

    if (data.results && data.results.length > 0) {
      renderScraperResults(data.results);
    } else {
      grid.innerHTML = `<div class="col-span-3 text-center text-slate-500 py-8 text-xs font-mono">No se encontraron resultados para "${q}". Intenta con otros términos.</div>`;
    }
  } catch (e) {
    loading.classList.add("hidden");
    grid.innerHTML = `<div class="col-span-3 text-center text-rose-400 py-8 text-xs">Error en scraping: ${e.message}</div>`;
  }
}

function renderScraperResults(items) {
  const grid = document.getElementById("scraperGrid");
  grid.innerHTML = "";

  items.forEach(item => {
    const card = document.createElement("div");
    card.className = "bg-slate-950 p-4 rounded-xl border border-slate-800 hover:border-sky-500/50 transition flex flex-col justify-between space-y-3";

    const isVideo = item.type === "video";
    const icon = isVideo ? "fa-brands fa-youtube text-rose-400" : "fa-solid fa-globe text-sky-400";
    const viewsBadge = item.views ? `<span class="text-[10px] text-slate-500">${(item.views/1000).toFixed(0)}k vistas</span>` : "";

    card.innerHTML = `
      <div class="space-y-2">
        <div class="flex items-center justify-between text-xs">
          <span class="flex items-center gap-1.5 font-medium text-slate-400">
            <i class="${icon}"></i> ${item.source}
          </span>
          <span class="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-800 text-slate-300 border border-slate-700">
            ${item.badge}
          </span>
        </div>
        <h4 class="text-xs font-bold text-white leading-snug line-clamp-2">${item.title}</h4>
        <p class="text-[11px] text-slate-400 line-clamp-2">${item.snippet || 'Estrategia con indicadores técnicos y reglas de entrada/salida.'}</p>
      </div>

      <div class="pt-2 border-t border-slate-800/80 flex items-center justify-between">
        ${viewsBadge}
        <button onclick="importScrapedItem('${encodeURIComponent(item.url)}', '${encodeURIComponent(item.title)}', '${item.type}')" 
                class="px-3 py-1.5 rounded-lg bg-sky-600/20 hover:bg-sky-600 border border-sky-500/30 text-sky-300 hover:text-white text-xs font-semibold flex items-center gap-1.5 transition ml-auto">
          <i class="fa-solid fa-bolt"></i> Importar a MQL5
        </button>
      </div>
    `;
    grid.appendChild(card);
  });
}

async function importScrapedItem(encodedUrl, encodedTitle, type) {
  const url = decodeURIComponent(encodedUrl);
  const title = decodeURIComponent(encodedTitle);

  showLoading(true, `Importando y formalizando reglas de: "${title.slice(0, 30)}..." con IA`);
  switchTab("tab-ingest");

  try {
    const res = await fetch("/api/scraper/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url, title: title, type: type })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || data.message || "Error al importar estrategia");
    }
    handleExtractionSuccess(data);
  } catch (err) {
    alert("Error al importar estrategia: " + err.message);
  } finally {
    showLoading(false);
  }
}

// ==================== MANUAL EXTRACTION ====================

function loadSampleStrategy(sampleId) {
  const inputTxt = document.getElementById("inputText");
  if (sampleId === 1) {
    inputTxt.value = `Estrategia EMA Crossover M15 en EURUSD/GBPUSD:
- Indicadores: EMA rápida de 9 periodos y EMA lenta de 21 periodos aplicadas al cierre.
- Entrada Long (Compra): Cuando la EMA 9 cruce hacia arriba la EMA 21 en vela cerrada.
- Entrada Short (Venta): Cuando la EMA 9 cruce hacia abajo la EMA 21 en vela cerrada.
- Salida Long: Cuando la EMA 9 cruce hacia abajo la EMA 21.
- Salida Short: Cuando la EMA 9 cruce hacia arriba la EMA 21.
- Gestión de riesgo: Stop Loss de 25 pips, Take Profit de 50 pips. Lote de 0.01.`;
  } else {
    inputTxt.value = `Estrategia RSI Pullback H1:
- Indicadores: EMA de 200 periodos para tendencia macro, y RSI de 14 periodos.
- Regla Compra: Precio por encima de la EMA 200 y RSI cruza hacia arriba el nivel 30 (sobreventa).
- Regla Venta: Precio por debajo de la EMA 200 y RSI cruza hacia abajo el nivel 70 (sobrecompra).
- Stop Loss: 40 pips. Take Profit: 80 pips (Ratio 1:2).`;
  }
}

async function processText() {
  const content = document.getElementById("inputText").value.trim();
  if (!content) return alert("Por favor escribe o selecciona un ejemplo de estrategia.");

  showLoading(true, "Analizando reglas de la estrategia con IA...");
  try {
    const res = await fetch("/api/extract/text", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: "Estrategia Extraída", content: content })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || data.message || "Error del servidor al analizar texto");
    }
    handleExtractionSuccess(data);
  } catch (e) {
    alert("Error al extraer estrategia: " + e.message);
  } finally {
    showLoading(false);
  }
}

async function processUrl() {
  const url = document.getElementById("inputUrl").value.trim();
  if (!url) return alert("Por favor pega un enlace de YouTube, TikTok o Reel.");

  showLoading(true, "Descargando audio/video y analizando trading setup con IA...");
  try {
    const res = await fetch("/api/extract/url", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url: url })
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || data.message || "Error del servidor al procesar la URL");
    }
    handleExtractionSuccess(data);
  } catch (e) {
    alert("Error procesando URL: " + e.message);
  } finally {
    showLoading(false);
  }
}

async function handlePdfUpload(event) {
  const file = event.target.files[0];
  if (!file) return;

  document.getElementById("pdfSelectedName").innerText = "Archivo: " + file.name;
  document.getElementById("pdfSelectedName").classList.remove("hidden");

  const formData = new FormData();
  formData.append("file", file);

  showLoading(true, "Extrayendo texto y analizando estrategia del PDF con IA...");
  try {
    const res = await fetch("/api/extract/pdf", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || data.message || "Error del servidor al procesar el PDF");
    }
    handleExtractionSuccess(data);
  } catch (e) {
    alert("Error procesando PDF: " + e.message);
  } finally {
    showLoading(false);
  }
}

function handleExtractionSuccess(data) {
  if (!data || !data.strategy) {
    alert("No se pudo obtener la estrategia: " + (data && (data.detail || data.error || data.message) || "Respuesta incompleta"));
    return;
  }
  currentStrategy = data.strategy;
  currentMql5Code = data.mql5_code || "";
  currentAudit = data.audit || {};

  // Actualizar previsualización en pestaña 1
  document.getElementById("prevName").innerText = currentStrategy.name || "Estrategia IA";
  const syms = (currentStrategy.recommended_symbols || ["EURUSD"]).join(", ");
  const tf = currentStrategy.recommended_timeframe || "H1";
  document.getElementById("prevTf").innerText = `${syms} (${tf})`;
  let indsDisplay = "";
  if (currentAudit && currentAudit.indicators && currentAudit.indicators.length > 0) {
    indsDisplay = currentAudit.indicators.map(i => i.name).join(", ");
  } else if (currentStrategy && currentStrategy.indicators && currentStrategy.indicators.length > 0) {
    indsDisplay = currentStrategy.indicators.map(i => i.name).join(", ");
  } else {
    indsDisplay = "Acción del Precio Pura (Sin Indicadores)";
  }
  document.getElementById("prevIndicators").innerText = indsDisplay;

  // Rellenar pestaña 3: Auditoría & Extracción Exhaustiva
  renderAuditData(currentAudit, currentStrategy);

  // Cambiar al Paso 3: Auditoría & Extracción de Reglas
  switchTab("tab-audit");
}

function renderAuditData(audit, strategy) {
  document.getElementById("auditTitle").innerText = audit.title || strategy.name || "Estrategia Extraída";
  document.getElementById("auditTraderBadge").innerText = audit.trader || "Trader Profesional";
  document.getElementById("auditSummary").innerText = audit.summary || strategy.description || "Análisis de estrategia institucional.";
  document.getElementById("auditTimeframe").innerText = audit.timeframe || (strategy.recommended_timeframe || "M15");
  document.getElementById("auditSymbols").innerText = (audit.symbols || strategy.recommended_symbols || ["EURUSD"]).join(", ");

  // Horarios de Operativa & Sesiones
  const th = audit.trading_hours || {};
  if (document.getElementById("auditSessionName")) {
    document.getElementById("auditSessionName").innerText = th.session_name || "New York / London";
  }
  if (document.getElementById("auditOperatingWindow")) {
    document.getElementById("auditOperatingWindow").innerText = th.operating_window || "13:30 - 20:00 UTC";
  }
  if (document.getElementById("auditSessionDays")) {
    document.getElementById("auditSessionDays").innerText = th.days || "Lunes a Viernes";
  }
  if (document.getElementById("auditSessionNotes")) {
    document.getElementById("auditSessionNotes").innerText = th.notes || "Operar en momentos de alta liquidez y volumen institucional.";
  }

  // Activos & Especificación del Mercado
  const mas = audit.market_asset_spec || {};
  if (document.getElementById("auditAssetClass")) {
    document.getElementById("auditAssetClass").innerText = mas.asset_class || "Forex / Índices";
  }
  if (document.getElementById("auditMaxSpread")) {
    document.getElementById("auditMaxSpread").innerText = mas.max_spread || ((strategy.max_spread_points || 35) + " pts");
  }
  if (document.getElementById("auditAccountType")) {
    document.getElementById("auditAccountType").innerText = mas.account_recommendation || "Cuentas ECN / RAW Spread con baja latencia.";
  }

  // Renderizar lista de indicadores específicos
  const indList = document.getElementById("auditIndicatorsList");
  indList.innerHTML = "";
  const indicators = audit.indicators || [];
  if (indicators.length === 0 && strategy.indicators) {
    strategy.indicators.forEach(ind => {
      indicators.push({
        name: ind.name,
        category: "Nativo MT5",
        parameters: ind.init_call,
        description: "Indicador incorporado en la lógica algorítmica."
      });
    });
  }

  indicators.forEach(ind => {
    const isCustom = ind.is_custom || (ind.category && ind.category.toLowerCase().includes("custom"));
    const badgeClass = isCustom ? "bg-purple-500/20 text-purple-300 border-purple-500/30" : "bg-emerald-500/20 text-emerald-300 border-emerald-500/30";
    const badgeText = isCustom ? "Custom / Order Flow" : "Nativo MT5";
    const card = document.createElement("div");
    card.className = "p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5";
    card.innerHTML = `
      <div class="flex items-center justify-between">
        <span class="text-xs font-bold text-white flex items-center gap-2">
          <i class="fa-solid fa-chart-line text-sky-400"></i> ${ind.name}
        </span>
        <span class="text-[10px] px-2 py-0.5 rounded-full border font-mono ${badgeClass}">${badgeText}</span>
      </div>
      <div class="text-[11px] text-slate-400 font-mono"><strong class="text-slate-300">Parámetros:</strong> ${ind.parameters || "N/A"}</div>
      <div class="text-[11px] text-slate-300 leading-relaxed font-sans">${ind.description || ""}</div>
    `;
    indList.appendChild(card);
  });

  // Renderizar Reglas de Entrada, Gatillos & Invalidación
  const rules = audit.entry_rules || {};
  if (document.getElementById("auditMarketContext")) {
    document.getElementById("auditMarketContext").innerText = rules.market_context || "Contexto de estructura y liquidez institucional.";
  }
  document.getElementById("auditRuleLong").innerText = rules.long || strategy.entry_buy_code || "Sin condición";
  document.getElementById("auditRuleShort").innerText = rules.short || strategy.entry_sell_code || "Sin condición";
  if (document.getElementById("auditTrigger")) {
    document.getElementById("auditTrigger").innerText = rules.trigger || "Apertura de vela siguiente al confirmarse el setup.";
  }
  document.getElementById("auditConfirmation").innerText = rules.confirmation || "Esperar confirmación por cierre de vela.";
  if (document.getElementById("auditInvalidation")) {
    document.getElementById("auditInvalidation").innerText = rules.invalidation || "Invalidar si el spread supera la tolerancia máxima o falla el cierre.";
  }

  // Renderizar Gestión de Riesgo & Lot Sizing
  const rm = audit.risk_management || {};
  document.getElementById("auditSL").innerText = rm.stop_loss || ((strategy.stop_loss_points ? strategy.stop_loss_points/10 : 20) + " pips");
  document.getElementById("auditTP").innerText = rm.take_profit || ((strategy.take_profit_points ? strategy.take_profit_points/10 : 60) + " pips");
  document.getElementById("auditBE").innerText = rm.breakeven || ("+" + (strategy.breakeven_pips || 15) + " pips");
  document.getElementById("auditTrailing").innerText = rm.trailing_stop || ((strategy.trailing_stop_pips || 12) + " pips");
  document.getElementById("auditRR").innerText = rm.risk_reward_ratio || "Ratio 1:3";
  if (document.getElementById("auditLotSizing")) {
    document.getElementById("auditLotSizing").innerText = rm.lot_sizing || "0.01 lotes por cada $1,000 o 1% de riesgo institucional.";
  }
  document.getElementById("auditSecrets").innerText = audit.secrets_and_traps || "Gestión disciplinada de riesgo y paciencia.";

  // Sincronizar automáticamente el panel izquierdo del Paso 4
  syncStrategyToMql5Panel(audit, strategy, currentMql5Code);
}

function syncStrategyToMql5Panel(audit, strategy, mql5Code) {
  if (!strategy) return;
  const safeName = strategy.name || "AI_Strategy";
  const mqlInput = document.getElementById("mqlName");
  if (mqlInput) mqlInput.value = safeName;
  
  const mqlFile = document.getElementById("mqlFileName");
  if (mqlFile) mqlFile.innerText = `${safeName}.mq5`;

  // Activo & Timeframe
  const assetEl = document.getElementById("logicAsset");
  if (assetEl) assetEl.innerText = (audit?.symbols || strategy.recommended_symbols || ["EURUSD"]).join(", ");

  const tfEl = document.getElementById("logicTf");
  if (tfEl) tfEl.innerText = audit?.timeframe || strategy.recommended_timeframe || "M15";

  // Horario de Servidor MT5
  const hoursEl = document.getElementById("logicServerHours");
  if (hoursEl) {
    if (audit?.trading_hours?.operating_window) {
      hoursEl.innerText = audit.trading_hours.operating_window;
    } else {
      const sh = String(strategy.start_hour ?? 15).padStart(2, '0');
      const sm = String(strategy.start_minute ?? 0).padStart(2, '0');
      const eh = String(strategy.end_hour ?? 17).padStart(2, '0');
      const em = String(strategy.end_minute ?? 0).padStart(2, '0');
      hoursEl.innerText = `${sh}:${sm} - ${eh}:${em} MT5 (Servidor)`;
    }
  }

  // Indicadores / Lógica
  const indEl = document.getElementById("logicIndicators");
  if (indEl) {
    if (audit?.indicators && audit.indicators.length > 0) {
      indEl.innerText = audit.indicators.map(i => i.name).join(", ");
    } else if (strategy.indicators && strategy.indicators.length > 0) {
      indEl.innerText = strategy.indicators.map(i => i.name).join(", ");
    } else {
      indEl.innerText = "Acción del Precio Pura (Sin Indicadores)";
    }
  }

  // Reglas C++
  const buyEl = document.getElementById("logicBuy");
  if (buyEl) buyEl.innerText = strategy.entry_buy_code || "Sin condición";

  const sellEl = document.getElementById("logicSell");
  if (sellEl) sellEl.innerText = strategy.entry_sell_code || "Sin condición";

  // Gestión de Riesgo
  const slEl = document.getElementById("logicSL");
  if (slEl) {
    slEl.innerText = audit?.risk_management?.stop_loss || 
      (strategy.stop_loss_points ? (strategy.stop_loss_points / 10) + " pips" : "25 pips");
  }

  const tpEl = document.getElementById("logicTP");
  if (tpEl) {
    tpEl.innerText = audit?.risk_management?.take_profit || 
      (strategy.take_profit_points ? (strategy.take_profit_points / 10) + " pips" : "50 pips");
  }

  const rrEl = document.getElementById("logicRR");
  if (rrEl) {
    rrEl.innerText = audit?.risk_management?.risk_reward_ratio || "1:1";
  }

  // Editor MQL5
  const editorEl = document.getElementById("mqlCodeEditor");
  if (editorEl && mql5Code) editorEl.value = mql5Code;
}

async function proceedToMql5Generation() {
  const btn = document.getElementById("btnProceedMql5");
  btn.disabled = true;
  btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Generando MQL5...`;

  try {
    if (!currentMql5Code && currentStrategy) {
      const res = await fetch("/api/strategy/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ strategy: currentStrategy })
      });
      const data = await res.json();
      if (data.success && data.mql5_code) {
        currentMql5Code = data.mql5_code;
      }
    }

    // Sincronizar todos los campos hacia el Paso 4
    syncStrategyToMql5Panel(currentAudit, currentStrategy, currentMql5Code);

    // Pasar al Paso 4: Código MQL5 & Compilación
    switchTab("tab-mql5");
  } catch (err) {
    alert("Error generando MQL5: " + err.message);
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<span>⚡ Paso 4: Generar EA en MQL5 con estas Reglas</span> <i class="fa-solid fa-arrow-right"></i>`;
  }
}

function showLoading(show, message = "") {
  const p = document.getElementById("extractionProgress");
  const label = document.getElementById("extractionStatusLabel");
  if (show) {
    p.classList.remove("hidden");
    label.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin text-emerald-400"></i> ${message}`;
  } else {
    p.classList.add("hidden");
  }
}

// ==================== COMPILATION ====================

async function compileMql5() {
  const code = document.getElementById("mqlCodeEditor").value;
  const eaName = (document.getElementById("mqlName").value || "AI_Strategy").trim();
  const btn = document.getElementById("btnCompile");
  const fb = document.getElementById("compileFeedback");

  btn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Compilando en MetaEditor...`;
  btn.disabled = true;

  try {
    const res = await fetch("/api/compile", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ mql5_code: code, ea_name: eaName })
    });
    const data = await res.json();
    fb.classList.remove("hidden");

    if (data.success) {
      fb.className = "mt-3 text-xs font-mono p-3 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-300";
      fb.innerHTML = `<strong>✅ Compilación Exitosa en MetaTrader 5 (0 errores, 0 warnings)</strong><br><span class="text-slate-300">Expert Advisor (.ex5) compilado y disponible en: <code>${data.relative_ea || 'Experts/' + eaName + '.ex5'}</code></span>`;
    } else {
      fb.className = "mt-3 text-xs font-mono p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300";
      fb.innerHTML = `<strong>❌ Error de Compilación:</strong><br><pre class="text-[10px] mt-1 whitespace-pre-wrap">${data.log || data.message || "Error al compilar en MetaEditor"}</pre>`;
    }
  } catch (err) {
    fb.classList.remove("hidden");
    fb.className = "mt-3 text-xs font-mono p-3 rounded-lg bg-rose-950/60 border border-rose-800 text-rose-300";
    fb.innerText = "Error de conexión: " + err.message;
  } finally {
    btn.innerHTML = `<i class="fa-solid fa-gears"></i> Compilar MQL5 en MetaTrader 5`;
    btn.disabled = false;
  }
}

function copyMqlCode() {
  const code = document.getElementById("mqlCodeEditor").value;
  if (!code) return alert("No hay código MQL5 para copiar.");
  navigator.clipboard.writeText(code);
  alert("Código MQL5 copiado al portapapeles.");
}

function downloadMqlFile() {
  const code = document.getElementById("mqlCodeEditor").value;
  if (!code) return alert("No hay código MQL5 para descargar.");
  const eaName = (document.getElementById("mqlName").value || "AI_Strategy").replace(/[^a-zA-Z0-9_]/g, "_");
  const blob = new Blob([code], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${eaName}.mq5`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}
