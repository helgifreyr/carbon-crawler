@echo off
rem The act editor; give a template name to open another (default caves): run_act_editor.cmd caves
if not "%~1"=="" set ARPG_ACT=%~1
pwsh -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_demo.ps1" -Script "%~dp0demo\act_editor.py" -RunName act_editor
exit /b %ERRORLEVEL%
