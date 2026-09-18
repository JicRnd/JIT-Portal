@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo The virtual environment is missing.
    echo Run BUILD_AND_RUN_CYLINDER_QUOTE.py again to repair the installation.
    pause
    exit /b 1
)
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" (
    start "" "%ProgramFiles%\Google\Chrome\Application\chrome.exe" http://127.0.0.1:5055
) else if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" (
    start "" "%LocalAppData%\Google\Chrome\Application\chrome.exe" http://127.0.0.1:5055
) else (
    start "" http://127.0.0.1:5055
)
.venv\Scripts\python.exe run.py
pause
