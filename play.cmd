@echo off
setlocal DisableDelayedExpansion
"%~dp0runtime\python.exe" -B -X utf8 "%~dp0app\player.py" %*
exit /b %errorlevel%
