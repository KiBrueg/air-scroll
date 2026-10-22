@echo off
setlocal
cd /d "%~dp0"
set "PYTHONHOME="
set "PYTHONPATH="
set "PYTHONNOUSERSITE=1"
if not exist ".venv\Scripts\python.exe" (
  echo Air Scroll environment is missing. Run "Start Air Scroll.bat" once first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" app.py
