@echo off
if "%TICK_MS%"=="" set TICK_MS=10
echo ARPG server: %TICK_MS% ms ticks on port 47400. Ctrl+C to stop.
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1" -Script "%~dp0demo\arpg_server.py" -RunName arpg_server %*
exit /b %ERRORLEVEL%
