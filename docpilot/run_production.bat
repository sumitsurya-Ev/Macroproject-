@echo off
title DocPilot Production Server
cd /d "%~dp0"
echo Starting DocPilot Production Server (Waitress WSGI)...
python run_production.py
pause
