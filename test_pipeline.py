import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mt5_mcp_client import MT5MCPClient
from mql5_generator import MQL5Generator

# 1. Define sample strategy (EMA Cross)
strategy_spec = {
    "name": "AI_EMA_Cross_Test",
    "description": "Fast EMA crosses Slow EMA test strategy",
    "default_lot": 0.01,
    "stop_loss_points": 250,
    "take_profit_points": 500,
    "magic_number": 888123,
    "custom_inputs": [
        {"type": "int", "name": "InpFastPeriod", "default": 9, "comment": "Fast EMA Period"},
        {"type": "int", "name": "InpSlowPeriod", "default": 21, "comment": "Slow EMA Period"}
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
    # Cross condition: buf[0] is candle 1 (closed), buf[1] is candle 2
    "entry_buy_code": "buf_fast_ema[0] > buf_slow_ema[0] && buf_fast_ema[1] <= buf_slow_ema[1]",
    "entry_sell_code": "buf_fast_ema[0] < buf_slow_ema[0] && buf_fast_ema[1] >= buf_slow_ema[1]",
    "exit_buy_code": "buf_fast_ema[0] < buf_slow_ema[0]",
    "exit_sell_code": "buf_fast_ema[0] > buf_slow_ema[0]"
}

print("1. Generating MQL5 code...")
mql5_code = MQL5Generator.generate(strategy_spec)

client = MT5MCPClient()
print("2. Connecting to MT5 MCP...")
if client.initialize():
    print("   Connected! Experts folder:", client.get_experts_folder())
else:
    print("   Failed to connect to MCP!")
    sys.exit(1)

print("3. Compiling EA...")
compile_res = client.save_and_compile_ea(mql5_code, "AI_EMA_Cross_Test.mq5")
print("   Compilation Success:", compile_res["success"])
print("   Log:", compile_res["log"])

if not compile_res["success"]:
    print("Compilation failed!")
    sys.exit(1)

print("4. Testing complete backtest execution...")
backtest_res = client.run_backtest_pipeline(
    ea_compiled_path=compile_res["compiled_path"],
    symbol="EURUSD",
    timeframe="M15",
    from_date="2025-01-01T00:00:00",
    to_date="2025-01-15T00:00:00",
    deposit=10000.0,
    model="open prices", # Fast for test verification
    timeout_sec=60
)
print("5. Backtest Finished! Run ID:", backtest_res["run_id"])
print("Report Summary:")
print(str(backtest_res["report"])[:500] + "...")
