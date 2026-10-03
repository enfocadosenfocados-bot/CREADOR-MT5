import os
import re
import json
import subprocess
from typing import Dict, Any, Optional, List
import pdfplumber
import yt_dlp
from google import genai
from google.genai import types

class StrategyExtractor:
    """Multimodal strategy extractor from URLs (YouTube, Reels, TikTok), PDFs, or text."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        # Read from environment or argument
        self.api_key = gemini_api_key or os.getenv("GEMINI_API_KEY")
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None

    def extract_from_pdf(self, pdf_path: str) -> str:
        """Extract text and metadata from PDF strategy file."""
        text_content = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                text = page.extract_text()
                if text:
                    text_content.append(f"--- Page {page_idx + 1} ---\n{text}")
        return "\n\n".join(text_content)

    def download_media_from_url(self, url: str, output_dir: str) -> Dict[str, Any]:
        """Download audio/video and metadata using yt-dlp."""
        os.makedirs(output_dir, exist_ok=True)
        ydl_opts = {
            'outtmpl': os.path.join(output_dir, '%(id)s.%(ext)s'),
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'no_warnings': True,
        }
        
        info_dict = {}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            info_dict = {
                "title": info.get("title", ""),
                "description": info.get("description", ""),
                "duration": info.get("duration", 0),
                "id": info.get("id", ""),
                "audio_path": os.path.join(output_dir, f"{info.get('id')}.mp3")
            }
        return info_dict

    def analyze_strategy_text(self, raw_text: str, context_title: str = "") -> Dict[str, Any]:
        """
        Analyze extracted trading strategy text/transcript and convert it into
        the standardized MQL5 strategy JSON specification.
        """
        prompt = f"""
You are an institutional algorithmic trading expert and senior MQL5 developer.
Analyze the following trading strategy material (from video transcript, PDF or article) titled "{context_title}".

Extract and formalize the trading strategy into a STRICT JSON specification matching this exact schema:

{{
  "name": "Strategy_Pascal_Case_Name",
  "description": "Clear explanation of the strategy logic",
  "recommended_symbols": ["EURUSD", "GBPUSD"],
  "recommended_timeframe": "M15",
  "default_lot": 0.01,
  "stop_loss_points": 300,
  "take_profit_points": 600,
  "magic_number": 123456,
  "custom_inputs": [
    {{"type": "int", "name": "InpFastEMA", "default": 20, "comment": "Fast EMA period"}},
    {{"type": "int", "name": "InpSlowEMA", "default": 50, "comment": "Slow EMA period"}}
  ],
  "indicators": [
    {{
      "name": "Fast_EMA",
      "handle_var": "h_fast_ema",
      "buffer_var": "buf_fast_ema",
      "init_call": "iMA(_Symbol, _Period, InpFastEMA, 0, MODE_EMA, PRICE_CLOSE)"
    }},
    {{
      "name": "Slow_EMA",
      "handle_var": "h_slow_ema",
      "buffer_var": "buf_slow_ema",
      "init_call": "iMA(_Symbol, _Period, InpSlowEMA, 0, MODE_EMA, PRICE_CLOSE)"
    }}
  ],
  "entry_buy_code": "C++ / MQL5 boolean expression using buffer arrays (buf_xxx[0] is candle 1, buf_xxx[1] is candle 2, rates[0] is candle 1)",
  "entry_sell_code": "C++ / MQL5 boolean expression for sell",
  "exit_buy_code": "C++ / MQL5 boolean expression or false",
  "exit_sell_code": "C++ / MQL5 boolean expression or false"
}}

IMPORTANT RULES FOR MQL5 CODE:
1. All indicator init_call MUST use valid MetaTrader 5 native functions (e.g. iMA, iRSI, iMACD, iBands, iATR, iStochastic).
2. Buffer indexing: buf[0] is candle shift 1 (most recently closed candle). buf[1] is candle shift 2.
3. Rates array: rates[0].close is candle 1 close, rates[0].open is candle 1 open, rates[0].high is candle 1 high, rates[0].low is candle 1 low.
4. Output MUST be ONLY the raw JSON object, no markdown backticks.

MATERIAL TO ANALYZE:
{raw_text}
"""
        if not self.client:
            # Fallback heuristic or mock if API key is not yet set
            raise ValueError("GEMINI_API_KEY is not configured. Please set the API key in settings.")

        response = self.client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        return json.loads(response.text)
