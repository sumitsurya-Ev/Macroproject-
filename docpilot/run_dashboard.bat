@echo off
title DocPilot
cd /d "%~dp0"

echo.
echo  ██████╗  ██████╗  ██████╗
echo  ██╔══██╗██╔═══██╗██╔════╝
echo  ██║  ██║██║   ██║██║
echo  ██║  ██║██║   ██║██║
echo  ██████╔╝╚██████╔╝╚██████╗
echo  ╚═════╝  ╚═════╝  ╚═════╝   Pilot
echo.
echo  Intelligent Document Filing System
echo  ─────────────────────────────────────────────
echo.

:: Load .env file if it exists
if exist .env (
  for /f "usebackq tokens=1,2 delims==" %%A in (".env") do (
    set "%%A=%%B"
  )
  echo  [OK] Loaded API keys from .env
) else (
  echo  [INFO] No .env file found - running in Keyword mode
  echo  [INFO] Go to http://127.0.0.1:5000/settings to add your API key
)

echo.
echo  Starting server at http://127.0.0.1:5000
echo  Press Ctrl+C to stop.
echo  Opening browser...
echo  ─────────────────────────────────────────────
echo.

start "" "http://127.0.0.1:5000"
python app.py

pause
