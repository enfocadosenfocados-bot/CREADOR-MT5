import subprocess
import json
import re
import urllib.request
import urllib.parse
from typing import List, Dict, Any, Optional
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup

class StrategyScraper:
    """Exhaustive scraper for trading strategies across YouTube, Social Media, and Web/Forums."""

    @staticmethod
    def search_youtube(query: str, limit: int = 6) -> List[Dict[str, Any]]:
        """Search YouTube and video platforms for trading strategies using yt-dlp."""
        cmd = [
            'yt-dlp',
            '--default-search', f'ytsearch{limit}',
            query,
            '--dump-single-json',
            '--flat-playlist',
            '--no-warnings',
            '--quiet'
        ]
        results = []
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            if res.stdout:
                data = json.loads(res.stdout)
                for e in data.get('entries', []):
                    results.append({
                        "id": e.get("id"),
                        "title": e.get("title"),
                        "url": f"https://www.youtube.com/watch?v={e.get('id')}",
                        "author": e.get("channel") or e.get("uploader") or "Trader",
                        "duration": e.get("duration"),
                        "views": e.get("view_count", 0),
                        "source": "YouTube",
                        "badge": "Video Strategy",
                        "type": "video"
                    })
        except Exception as ex:
            print("YouTube search error:", ex)
        return results

    @staticmethod
    def search_web(query: str, limit: int = 8) -> List[Dict[str, Any]]:
        """Search Web forums, TradingView ideas, and Quant blogs."""
        results = []
        try:
            ddgs = DDGS()
            raw_results = list(ddgs.text(query, max_results=limit))
            for r in raw_results:
                title = r.get("title", "")
                url = r.get("href", "")
                body = r.get("body", "")
                
                # Determine source badge
                source = "Web"
                if "forexfactory.com" in url:
                    source = "Forex Factory"
                elif "tradingview.com" in url:
                    source = "TradingView"
                elif "reddit.com" in url:
                    source = "Reddit"
                elif "mql5.com" in url:
                    source = "MQL5 Community"
                    
                results.append({
                    "id": url,
                    "title": title,
                    "url": url,
                    "snippet": body,
                    "author": source,
                    "source": source,
                    "badge": "Forum / Article",
                    "type": "article"
                })
        except Exception as ex:
            print("Web search error:", ex)
        return results

    @staticmethod
    def scrape_url_content(url: str) -> str:
        """Fetch and extract clean text from any web strategy page or forum post."""
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8', errors='ignore')
                soup = BeautifulSoup(html, "html.parser")
                
                # Remove scripts, styles, navigation, footer
                for s in soup(["script", "style", "nav", "footer", "header", "aside"]):
                    s.decompose()
                    
                text = soup.get_text(separator="\n")
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                clean_text = "\n".join(lines[:120]) # Limit to key lines
                return clean_text
        except Exception as e:
            return f"Error extracting page content: {e}"

    @classmethod
    def exhaustive_search(cls, keyword: str = "profitable trading strategy", category: str = "all") -> List[Dict[str, Any]]:
        """Run multi-source search across videos and web forums."""
        combined = []
        
        if category in ["all", "video"]:
            yt_query = f"{keyword} trading strategy profitable backtest"
            combined.extend(cls.search_youtube(yt_query, limit=5))
            
        if category in ["all", "web"]:
            web_query = f"{keyword} strategy rules indicators forex trading"
            combined.extend(cls.search_web(web_query, limit=6))
            
        return combined
