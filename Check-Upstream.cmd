@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\Check-Upstream.ps1" %*
exit /b %ERRORLEVEL%
