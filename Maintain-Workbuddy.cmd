@echo off
setlocal
where pwsh.exe >nul 2>&1
if %ERRORLEVEL% EQU 0 (
  pwsh.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Maintain-Workbuddy.ps1" %*
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Maintain-Workbuddy.ps1" %*
)
exit /b %ERRORLEVEL%
