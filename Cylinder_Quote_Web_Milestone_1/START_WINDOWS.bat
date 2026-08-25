@echo off
setlocal
cd /d "%~dp0"
if not exist .venv (
  py -m venv .venv
)
call .venv\Scripts\activate.bat
py -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo Failed to install requirements. Check Internet/package access and try again.
  pause
  exit /b 1
)
py run.py
pause
