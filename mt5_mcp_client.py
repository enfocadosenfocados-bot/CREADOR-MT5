import requests
import json
import time
import os
import subprocess
from typing import Dict, Any, Optional, List

class MT5MCPClient:
    """Client for MetaTrader 5 Terminal and MetaEditor MCP endpoints."""

    def __init__(
        self,
        terminal_url: str = "http://127.0.0.1:22346/mcp",
        terminal_token: str = "LeTcvxDiAkFhhSvwJv+GPUyUWhT82Dzy3XWsgdVh4a",
        metaeditor_exe: str = r"C:\Program Files\MetaTrader 5\MetaEditor64.exe"
    ):
        self.terminal_url = terminal_url
        self.terminal_token = terminal_token
        self.metaeditor_exe = metaeditor_exe
        
        self.session = requests.Session()
        token = (self.terminal_token or "").strip()
        if token.lower().startswith("bearer "):
            token = token[7:].strip()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        })
        self._request_id = 1
        self._initialized = False
        self.workspace_info = None

    def initialize(self) -> bool:
        """Initialize MCP session with MetaTrader 5 Terminal."""
        init_payload = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "TradingStrategyStudio", "version": "1.0.0"}
            }
        }
        try:
            r = self.session.post(self.terminal_url, json=init_payload, timeout=10)
            if r.status_code == 200:
                self.session.post(
                    self.terminal_url,
                    json={"jsonrpc": "2.0", "method": "notifications/initialized"},
                    timeout=5
                )
                self._initialized = True
                
                # Fetch workspace info
                ws_res = self.call_tool("get_workspace_info", {})
                if ws_res and "structuredContent" in ws_res:
                    self.workspace_info = ws_res["structuredContent"].get("workspace", {})
                elif ws_res and "content" in ws_res:
                    try:
                        self.workspace_info = json.loads(ws_res["content"][0]["text"]).get("workspace", {})
                    except Exception:
                        pass
                return True
        except Exception as e:
            print(f"Error initializing Terminal MCP: {e}")
        return False

    def _get_next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call via MCP."""
        if not self._initialized:
            if not self.initialize():
                return {"error": "MCP Terminal initialization failed"}
            
        payload = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            }
        }
        try:
            res = self.session.post(self.terminal_url, json=payload, timeout=60)
            if res.status_code != 200:
                return {"error": f"HTTP {res.status_code}: {res.text[:200]}"}
            data = res.json()
            if "error" in data:
                return {"error": f"MCP Tool '{name}' error: {data['error']}"}
            return data.get("result", {})
        except Exception as e:
            return {"error": f"call_tool '{name}' exception: {str(e)}"}

    def _find_default_mql5_root(self) -> str:
        appdata = os.environ.get("APPDATA", "")
        terminal_base = os.path.join(appdata, "MetaQuotes", "Terminal")
        if os.path.exists(terminal_base):
            entries = sorted(
                [os.path.join(terminal_base, e) for e in os.listdir(terminal_base)],
                key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0,
                reverse=True
            )
            for folder in entries:
                mql5_path = os.path.join(folder, "MQL5")
                if os.path.isdir(mql5_path):
                    return mql5_path
        return os.path.join(os.path.dirname(__file__), "MQL5")

    def get_experts_folder(self) -> str:
        """Returns the Experts folder path in MQL5."""
        if not self.workspace_info:
            self.initialize()
        mql5_root = ""
        if self.workspace_info:
            mql5_root = self.workspace_info.get("mql5_folder", "")
        if not mql5_root:
            mql5_root = self._find_default_mql5_root()
        # We use CodexResearch subfolder as it's already cataloged by the running terminal
        target_dir = os.path.join(mql5_root, "Experts", "CodexResearch")
        os.makedirs(target_dir, exist_ok=True)
        return target_dir

    def get_tester_folder(self) -> str:
        """Returns the Tester Profiles folder path."""
        mql5_root = ""
        if self.workspace_info:
            mql5_root = self.workspace_info.get("mql5_folder", "")
        if not mql5_root:
            mql5_root = self._find_default_mql5_root()
        tester_dir = os.path.join(mql5_root, "Profiles", "Tester")
        os.makedirs(tester_dir, exist_ok=True)
        return tester_dir

    def save_and_compile_ea(self, mql5_code: str, ea_name: str = "studio_strategy") -> Dict[str, Any]:
        """Save MQL5 source code to CodexResearch folder and compile to .ex5."""
        if not ea_name.endswith(".mq5"):
            ea_name = f"{ea_name}.mq5"
            
        experts_dir = self.get_experts_folder()
        source_path = os.path.join(experts_dir, ea_name)
        compiled_path = os.path.splitext(source_path)[0] + ".ex5"
        log_path = os.path.splitext(source_path)[0] + ".log"
        
        # Write MQL5 file (UTF-8)
        with open(source_path, "w", encoding="utf-8") as f:
            f.write(mql5_code)
            
        # Compile using MetaEditor CLI
        if os.path.exists(self.metaeditor_exe):
            cmd = f'"{self.metaeditor_exe}" /compile:"{source_path}" /log:"{log_path}"'
            subprocess.run(cmd, shell=True, capture_output=True, text=True)
            
            # Read compilation log
            log_content = ""
            if os.path.exists(log_path):
                try:
                    with open(log_path, "r", encoding="utf-16") as lf:
                        log_content = lf.read()
                except Exception:
                    with open(log_path, "r", encoding="utf-8", errors="ignore") as lf:
                        log_content = lf.read()
                        
            compiled_success = os.path.exists(compiled_path)
            has_errors = " 0 errors," not in log_content if log_content else (not compiled_success)
            
            # Verify parameters via MCP if compiled
            ea_relative = f"CodexResearch\\{os.path.basename(compiled_path)}"
            params_data = None
            if compiled_success and not has_errors:
                try:
                    p_res = self.call_tool("get_expert_advisor_parameters", {"expert_path": compiled_path})
                    if not p_res.get("isError"):
                        params_data = json.loads(p_res["content"][0]["text"])
                except Exception as ex:
                    print(f"Error checking EA parameters: {ex}")

            return {
                "success": compiled_success and not has_errors,
                "source_path": source_path,
                "compiled_path": compiled_path,
                "relative_ea": ea_relative,
                "log": log_content,
                "parameters": params_data,
                "message": "0 errors - Compilation successful" if (compiled_success and not has_errors) else "Compilation error"
            }
        else:
            return {
                "success": False,
                "source_path": source_path,
                "compiled_path": None,
                "log": f"MetaEditor executable not found at {self.metaeditor_exe}",
                "message": "MetaEditor path invalid"
            }

    def run_backtest_pipeline(
        self,
        ea_relative_name: str,
        symbol: str = "EURUSD",
        timeframe: str = "H1",
        from_date: str = "2026.08.01",
        to_date: str = "2026.09.09",
        deposit: float = 10000.0,
        model: int = 1, # 1 = OHLC 1 minute, 0 = Every tick
        leverage: int = 100
    ) -> Dict[str, Any]:
        """
        Runs strategy tester backtest:
        1. Writes UTF-16 .ini configuration file directly
        2. Calls tester_run_backtest via MCP
        3. Returns run_id and initial status
        """
        tester_dir = self.get_tester_folder()
        config_name = f"studio_bt_{int(time.time())}.ini"
        config_path = os.path.join(tester_dir, config_name)
        
        ini_content = f"""[Tester]
Expert={ea_relative_name}
Optimization=0
Model={model}
OptimizationCriterion=6
Symbol={symbol}
Period={timeframe}
FromDate={from_date}
ToDate={to_date}
Deposit={deposit:.2f}
Currency=USD
Leverage={leverage}
ProfitInPips=0
ExecutionMode=0
Visual=0
ForwardMode=0
"""
        with open(config_path, "w", encoding="utf-16") as f:
            f.write(ini_content)

        run_res = self.call_tool("tester_run_backtest", {"config_path": config_path, "wait": False})
        
        if run_res.get("isError"):
            err_msg = run_res["content"][0]["text"] if run_res.get("content") else "Unknown error"
            return {"success": False, "error": err_msg}
            
        data = json.loads(run_res["content"][0]["text"])
        run_id = data.get("run_id")
        
        return {
            "success": data.get("ok", False),
            "run_id": run_id,
            "status": data.get("status", "started"),
            "config_path": config_path
        }

    def get_backtest_status(self, run_id: str) -> Dict[str, Any]:
        """Checks status of a running backtest."""
        res = self.call_tool("tester_get_status", {"run_id": run_id})
        if res.get("isError"):
            return {"status": "error", "message": res["content"][0]["text"]}
        return json.loads(res["content"][0]["text"])

    def get_backtest_report(self, run_id: str) -> Dict[str, Any]:
        """Fetches final backtest report in JSON format."""
        res = self.call_tool("tester_get_report", {"run_id": run_id, "file_format": "json"})
        if res.get("isError"):
            return {"error": res["content"][0]["text"]}
        return json.loads(res["content"][0]["text"])

    def get_account_summary(self) -> Dict[str, Any]:
        """Fetches account information and balances."""
        res = self.call_tool("get_trading_account_info", {})
        if res.get("isError"):
            return {}
        return json.loads(res["content"][0]["text"])

    def get_symbols(self) -> List[str]:
        """Fetches list of active symbols from Market Watch."""
        res = self.call_tool("get_marketwatch_symbols", {})
        if res.get("isError"):
            return ["EURUSD", "GBPUSD", "USDJPY", "BTCUSD", "US30"]
        data = json.loads(res["content"][0]["text"])
        return [s["symbol"] for s in data.get("symbols", [])]

    def get_time_info(self) -> Dict[str, Any]:
        """Fetches trade server and local time information from MT5 MCP."""
        try:
            res = self.call_tool("get_time_information", {})
            if not res.get("isError") and res.get("content"):
                return json.loads(res["content"][0]["text"])
        except Exception as e:
            print(f"Notice: Failed to fetch MT5 time information: {e}")
        return {}
