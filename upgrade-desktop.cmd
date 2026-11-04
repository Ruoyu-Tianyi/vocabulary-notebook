@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Please create the project .venv first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "tools\desktop_upgrade.py" %*
set "upgrade_result=%errorlevel%"
pause
exit /b %upgrade_result%
