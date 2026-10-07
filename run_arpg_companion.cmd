@echo off
rem An AI-controlled mage that joins the server like any other player (same NET_HOST / NET_PORT as the client).
if "%NET_HOST%"=="" set NET_HOST=127.0.0.1
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1" -Script "%~dp0demo\arpg_companion.py" -RunName arpg_companion_#
exit /b %ERRORLEVEL%
