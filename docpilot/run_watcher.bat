@echo off
title DocPilot Folder Watcher
cd /d "%~dp0"
echo ===================================================
echo   Starting DocPilot Folder Watcher...
echo   Drop PDFs into the 'incoming' folder!
echo ===================================================
python watcher.py
pause
