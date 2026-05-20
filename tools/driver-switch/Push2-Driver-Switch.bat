@echo off
REM Double-click wrapper for Push2-Driver-Switch.ps1
REM Uses -NoExit so this window also stays open if the .ps1 returns,
REM and bypasses PowerShell's default execution policy for this invocation.
REM The .ps1 itself self-elevates via UAC.
powershell.exe -NoProfile -NoExit -ExecutionPolicy Bypass -File "%~dp0Push2-Driver-Switch.ps1" %*
