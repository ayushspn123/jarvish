@echo off
REM Allow your phone to reach the JARVIS web app (opens port 8000 on the firewall).
REM RIGHT-CLICK this file and choose "Run as administrator". You only do this once.

netsh advfirewall firewall add rule name="JARVIS Web 8000" dir=in action=allow protocol=TCP localport=8000
if %errorlevel%==0 (
    echo.
    echo Done. Your phone can now reach JARVIS on port 8000.
) else (
    echo.
    echo Failed. Make sure you ran this as administrator.
)
pause
