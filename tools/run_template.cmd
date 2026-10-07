@echo off
setlocal
set "HERE=%~dp0"
set "PYTHONHOME=%HERE%python"
set "PYTHONPATH=%HERE%bin;%HERE%bin\python;%HERE%app;%HERE%python\Lib;%HERE%python\DLLs;%HERE%python\pydeps"
set "CARBON_BIN=%HERE%bin"
set "BUILDFLAVOR=internal"
set "PYTHONUNBUFFERED=1"
set "PATH=%HERE%bin;%SystemRoot%\System32;%SystemRoot%"
set "SCRIPT=%~1"
if "%SCRIPT%"=="" set "SCRIPT=trinity_viewer.py"
"%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -ExecutionPolicy Bypass -File "%HERE%run.ps1" -Script "%SCRIPT%"
exit /b %ERRORLEVEL%
