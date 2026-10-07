@echo off
rem run_arpg_client [companion [N]]: "companion" also starts N (default 1) AI mages fighting alongside you.
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_shaders.ps1" || exit /b 1
if /i "%~1"=="companion" (
    set COMPANIONS=%~2
    if "%~2"=="" set COMPANIONS=1
)
if defined COMPANIONS (
    for /l %%i in (1,1,%COMPANIONS%) do start "companion %%i" /min cmd /c "set COMPANION_SEED=%%i && "%~dp0run_arpg_companion.cmd""
)
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1" -Script "%~dp0demo\arpg_client.py" -RunName arpg_client_#
exit /b %ERRORLEVEL%
