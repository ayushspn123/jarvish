@echo off
REM Run JARVIS for your PHONE (or anywhere) via a public Cloudflare HTTPS tunnel.
REM No firewall, no certificate warning, no same-WiFi requirement.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    pause
    exit /b 1
)

echo Starting JARVIS web server (http://localhost:8000)...
start "JARVIS server" ".venv\Scripts\python.exe" -m webapp.server

echo Waiting for the server to boot...
timeout /t 4 /nobreak >nul

echo.
echo ============================================================
echo  Opening a public link. Look for the line that says:
echo     https://something-random.trycloudflare.com
echo  Open THAT link on your phone. (It changes each run.)
echo  Keep this window open while you use JARVIS.
echo ============================================================
echo.
cloudflared.exe tunnel --url http://localhost:8000
pause
