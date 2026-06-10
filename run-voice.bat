@echo off
REM Launch JARVIS in voice mode (microphone + speaker). Double-click this file to start.
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo Run setup first:  python -m venv .venv  ^&^&  .venv\Scripts\python.exe -m pip install -r requirements.txt
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m jarvis --voice
pause
