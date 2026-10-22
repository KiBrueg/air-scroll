@echo off
setlocal
cd /d "%~dp0"
rem Do not inherit packages from another Python installation.
set "PYTHONPATH="
set "PYTHONHOME="
if not exist ".venv\Scripts\python.exe" (
  echo Creating local Python environment...
  py -3.11 -m venv .venv || py -m venv .venv
)
echo Installing verified dependency versions on first start...
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check --require-hashes -r requirements.lock
if errorlevel 1 (
  echo.
  echo Setup failed. Read the error above; nothing was started.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" overlay.py
