@echo off
REM Launch the JARVIS web app. Open http://localhost:8000 in Chrome,
REM or http://<this-PC-ip>:8000 on your phone (same WiFi).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found. Run setup first.
    pause
    exit /b 1
)

echo Starting JARVIS web app on http://localhost:8000  (Ctrl+C to stop)
".venv\Scripts\python.exe" -m webapp.server
pause
