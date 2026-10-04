import os
import sys
import re
import json
import time
import shutil
from typing import Optional, Dict, Any, List
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from mt5_mcp_client import MT5MCPClient
from mql5_generator import MQL5Generator
from strategy_extractor import StrategyExtractor
from strategy_scraper import StrategyScraper

app = FastAPI(title="Trading Strategy Studio", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.json")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(UPLOAD_DIR, exist_ok=True)

def load_config() -> Dict[str, Any]:
    default_cfg = {
        "terminal_url": "http://127.0.0.1:22346/mcp",
        "terminal_token": "LeTcvxDiAkFhhSvwJv+GPUyUWhT82Dzy3XWsgdVh4a",
        "metaeditor_url": "http://127.0.0.1:22345/mcp",
        "metaeditor_token": "wr6HXl5UUn3f1ov4RTI/L+BQYoIFL+jj0gJ/wYJs8j",
        "metaeditor_exe": r"C:\Program Files\MetaTrader 5\MetaEditor64.exe",
        "gemini_api_key": ""
    }
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
                default_cfg.update(saved)
        except Exception:
            pass
    return default_cfg

def save_config(cfg: Dict[str, Any]):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

current_cfg = load_config()
mt5_client = MT5MCPClient(
    terminal_url=current_cfg.get("terminal_url", "http://127.0.0.1:22346/mcp"),
    terminal_token=current_cfg.get("terminal_token", ""),
    metaeditor_exe=current_cfg.get("metaeditor_exe", "")
)
strategy_extractor = StrategyExtractor(gemini_api_key=current_cfg.get("gemini_api_key"))

# Models
class ConfigUpdateRequest(BaseModel):
    terminal_url: str
    terminal_token: str
    metaeditor_url: Optional[str] = "http://127.0.0.1:22345/mcp"
    metaeditor_token: Optional[str] = ""
    metaeditor_exe: str
    gemini_api_key: Optional[str] = ""

class ExtractURLRequest(BaseModel):
    url: str

class ExtractTextRequest(BaseModel):
    title: str = "Estrategia Personalizada"
    content: str

class CompileRequest(BaseModel):
    mql5_code: str
    ea_name: str = "01_macd_pullback"

class BacktestRequest(BaseModel):
    ea_relative_name: str = "CodexResearch\\01_macd_pullback.ex5"
    symbol: str = "EURUSD"
    timeframe: str = "H1"
    from_date: str = "2026.08.01"
    to_date: str = "2026.09.09"
    deposit: float = 10000.0
    model: int = 1
    leverage: int = 100

class ImportScrapedRequest(BaseModel):
    url: str
    title: str
    type: str

@app.on_event("startup")
def startup_event():
    try:
        mt5_client.initialize()
    except Exception as e:
        print(f"Warning: MT5 MCP initialization at startup: {e}")

# ==================== CONFIGURATION ROUTES ====================

@app.get("/api/config")
def get_config_endpoint():
    return load_config()

@app.post("/api/config")
def update_config_endpoint(req: ConfigUpdateRequest):
    global mt5_client, strategy_extractor, current_cfg
    cfg_data = req.dict()
    save_config(cfg_data)
    current_cfg = cfg_data
    
    # Reinitialize client with new parameters dynamically
    mt5_client = MT5MCPClient(
        terminal_url=cfg_data["terminal_url"],
        terminal_token=cfg_data["terminal_token"],
        metaeditor_exe=cfg_data["metaeditor_exe"]
    )
    strategy_extractor = StrategyExtractor(gemini_api_key=cfg_data.get("gemini_api_key"))
    
    connected = False
    try:
        connected = mt5_client.initialize()
    except Exception as e:
        print("Reconnection error:", e)
        
    return {
        "success": True,
        "message": "Configuración actualizada correctamente.",
        "connected": connected
    }

# ==================== SYSTEM & MONITORING ROUTES ====================

@app.get("/api/system/status")
def get_system_status():
    try:
        connected = mt5_client.initialize()
        acc = mt5_client.get_account_summary()
        symbols = mt5_client.get_symbols()
        return {
            "status": "online" if connected else "offline",
            "account": acc.get("account", {}),
            "terminal": acc.get("terminal", {}),
            "symbols": symbols[:40] if symbols else ["EURUSD", "GBPUSD"]
        }
    except Exception as e:
        return {"status": "error", "message": str(e), "symbols": ["EURUSD", "GBPUSD"]}

# ==================== SCRAPING & RADAR ROUTES ====================

@app.get("/api/scraper/search")
def search_strategies_endpoint(q: str = "profitable trading strategy", category: str = "all"):
    """Exhaustive scraper across YouTube, TikTok/Reels, and Trading Web Forums."""
    try:
        results = StrategyScraper.exhaustive_search(keyword=q, category=category)
        return {
            "success": True,
            "query": q,
            "count": len(results),
            "results": results
        }
    except Exception as e:
        return {"success": False, "error": str(e), "results": []}

@app.post("/api/scraper/import")
def import_scraped_strategy_endpoint(req: ImportScrapedRequest):
    """Import any discovered strategy from web or video and feed directly into AI MQL5 pipeline."""
    try:
        content = ""
        if req.type == "video" or "youtube.com" in req.url or "youtu.be" in req.url:
            media = strategy_extractor.download_media_from_url(req.url, UPLOAD_DIR)
            transcript = media.get("transcript", "")
            content = f"Title: {media.get('title')}\nDescription: {media.get('description')}\n\nTranscript:\n{transcript}"
        else:
            page_text = StrategyScraper.scrape_url_content(req.url)
            content = f"Title: {req.title}\nSource: {req.url}\n\nContent:\n{page_text}"

        return extract_from_text(ExtractTextRequest(title=req.title, content=content))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error importing strategy: {str(e)}")

# ==================== STRATEGY EXTRACTION ROUTES ====================

class GenerateMql5Request(BaseModel):
    strategy: Dict[str, Any]

@app.post("/api/strategy/generate")
def generate_mql5_endpoint(req: GenerateMql5Request):
    try:
        code = MQL5Generator.generate(req.strategy)
        return {
            "success": True,
            "mql5_code": code
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/extract/text")
def extract_from_text(req: ExtractTextRequest):
    try:
        extraction = strategy_extractor.analyze_strategy_text(req.content, req.title)
        audit_data = extraction.get("audit") or {}
        strategy_data = extraction.get("strategy") or extraction
        mql5_code = MQL5Generator.generate(strategy_data)
        return {
            "success": True,
            "audit": audit_data,
            "strategy": strategy_data,
            "mql5_code": mql5_code
        }
    except Exception as e:
        print(f"Error in extract_from_text: {e}")
        from strategy_extractor import DeepStrategyAnalyzer
        fallback_res = DeepStrategyAnalyzer.analyze(req.content, req.title)
        audit_data = fallback_res.get("audit") or {}
        strategy_data = fallback_res.get("strategy") or fallback_res
        mql5_code = MQL5Generator.generate(strategy_data)
        return {
            "success": True,
            "warning": f"Nota: Analizado mediante DeepStrategyAnalyzer ({str(e)}).",
            "audit": audit_data,
            "strategy": strategy_data,
            "mql5_code": mql5_code
        }

@app.post("/api/extract/url")
def extract_from_url(req: ExtractURLRequest):
    try:
        media_info = strategy_extractor.download_media_from_url(req.url, UPLOAD_DIR)
        title = media_info.get("title", "Video Strategy")
        desc = media_info.get("description", "")
        transcript = media_info.get("transcript", "")
        content = f"Title: {title}\nDescription: {desc}\n\nTranscript:\n{transcript}"
        return extract_from_text(ExtractTextRequest(title=title, content=content))
    except Exception as e:
        print(f"Error downloading/extracting media: {e}")
        clean_title = "Video_Strategy"
        content = f"URL: {req.url}\nEstrategia algoritmica analizada."
        return extract_from_text(ExtractTextRequest(title=clean_title, content=content))

@app.post("/api/extract/pdf")
async def extract_from_pdf(file: UploadFile = File(...)):
    try:
        file_path = os.path.join(UPLOAD_DIR, file.filename)
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        pdf_text = strategy_extractor.extract_from_pdf(file_path)
        title = os.path.splitext(file.filename)[0]
        return extract_from_text(ExtractTextRequest(title=title, content=pdf_text))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading PDF: {str(e)}")

# ==================== COMPILATION & BACKTEST ROUTES ====================

@app.post("/api/compile")
def compile_ea(req: CompileRequest):
    try:
        res = mt5_client.save_and_compile_ea(req.mql5_code, req.ea_name)
        return res
    except Exception as e:
        return {"success": False, "log": str(e), "message": "Compilation failed with exception"}

@app.post("/api/backtest/run")
def run_backtest(req: BacktestRequest):
    try:
        res = mt5_client.run_backtest_pipeline(
            ea_relative_name=req.ea_relative_name,
            symbol=req.symbol,
            timeframe=req.timeframe,
            from_date=req.from_date,
            to_date=req.to_date,
            deposit=req.deposit,
            model=req.model,
            leverage=req.leverage
        )
        return res
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/backtest/status/{run_id}")
def check_status(run_id: str):
    try:
        data = mt5_client.get_backtest_status(run_id)
        status_text = data.get("tester_status", "").lower()
        finished = "stopped" in status_text or "finished" in status_text or "completed" in status_text
        return {
            "run_id": run_id,
            "status": data.get("tester_status", "unknown"),
            "progress_description": data.get("progress_description", ""),
            "finished": finished
        }
    except Exception as e:
        return {"run_id": run_id, "status": "error", "error": str(e), "finished": True}

@app.get("/api/backtest/report/{run_id}")
def get_report(run_id: str):
    try:
        rep = mt5_client.get_backtest_report(run_id)
        if "error" in rep:
            return {"success": False, "error": rep["error"]}
            
        profit = rep.get("profit", 0)
        profit_factor = rep.get("profit_factor", 0)
        drawdown_pct = rep.get("drawdown_percent_balance", 0)
        trades = rep.get("trades", 0)
        win_rate = (rep.get("profit_trades", 0) / trades * 100) if trades > 0 else 0

        verdict = "Estrategia Prometedora" if (profit > 0 and profit_factor > 1.3 and drawdown_pct < 15) else "Requiere Optimización"
        if profit <= 0:
            verdict = "Estrategia No Rentable (En este periodo/activo)"
            
        return {
            "success": True,
            "report": rep,
            "summary": {
                "profit": profit,
                "profit_factor": profit_factor,
                "drawdown_pct": drawdown_pct,
                "trades": trades,
                "win_rate": round(win_rate, 2),
                "sharpe_ratio": rep.get("sharpe_ratio", 0),
                "verdict": verdict
            }
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

# Serve frontend static assets
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8585, reload=True)
