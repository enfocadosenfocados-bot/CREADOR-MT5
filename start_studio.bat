@echo off
title Trading Strategy Studio (AI + MT5 MCP)
cd /d "%~dp0"
echo ========================================================
echo   TRADING STRATEGY STUDIO - AI MULTIMODAL & MT5 MCP
echo ========================================================
echo.
echo Iniciando servidor en http://127.0.0.1:8585 ...
start http://127.0.0.1:8585
"C:\Users\enfoc\AppData\Local\Programs\Python\Python313\python.exe" -m uvicorn server:app --host 127.0.0.1 --port 8585
pause
