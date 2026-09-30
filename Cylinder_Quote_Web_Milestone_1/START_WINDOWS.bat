@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
set "FLASK_DEBUG=1"
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Failed to install requirements. Check Internet/package access and try again.
  pause
  exit /b 1
)
.venv\Scripts\python.exe run.py
pause
