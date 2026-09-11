@echo off
setlocal EnableExtensions

rem Local AI launcher: Ollama models, cleaned chat gateway, then VS Code.
rem Double-click this file from any working directory. It starts only local services.

set "WORKSPACE=%~dp0"
if "%WORKSPACE:~-1%"=="\" set "WORKSPACE=%WORKSPACE:~0,-1%"
set "GATEWAY=%WORKSPACE%\.vscode\chat_gateway.py"
set "VENV_PYTHON=%WORKSPACE%\Cylinder_Quote_Web_Milestone_1\.venv\Scripts\python.exe"
set "OLLAMA_URL=http://127.0.0.1:11434"
set "GATEWAY_URL=http://127.0.0.1:8000/health"
set "PRIMARY_MODEL=qwen3-coder:30b"
set "SANITIZER_MODEL=llama3:latest"

rem Open VS Code first, before starting the local AI services.
call :open_vscode
if errorlevel 1 goto :startup_error

where ollama.exe >nul 2>&1
if errorlevel 1 (
    echo ERROR: ollama.exe was not found on PATH.
    exit /b 1
)

rem Start Ollama only when its local API is not responding.
curl.exe --silent --show-error --fail --max-time 5 "%OLLAMA_URL%/api/tags" >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start "Ollama" /min ollama.exe serve
    call :wait_for_url "%OLLAMA_URL%/api/tags" 20
    if errorlevel 1 (
        echo ERROR: Ollama did not become healthy.
        exit /b 1
    )
)

rem Models must already be installed. This launcher never downloads models.
echo Checking %PRIMARY_MODEL%...
call :check_model "%PRIMARY_MODEL%"
if errorlevel 1 goto :startup_error
echo Checking %SANITIZER_MODEL%...
call :check_model "%SANITIZER_MODEL%"
if errorlevel 1 goto :startup_error

if not exist "%GATEWAY%" (
    echo ERROR: Gateway not found: "%GATEWAY%"
    exit /b 1
)

rem Reuse a healthy gateway; otherwise start it in a separate background window.
curl.exe --silent --show-error --fail --max-time 5 "%GATEWAY_URL%" >nul 2>&1
if errorlevel 1 (
    if exist "%VENV_PYTHON%" (
        start "VS Code Local AI Gateway" /min cmd /d /c "cd /d ""%WORKSPACE%"" ^&^& ""%VENV_PYTHON%"" ""%GATEWAY%""
    ) else (
        start "VS Code Local AI Gateway" /min cmd /d /c "cd /d ""%WORKSPACE%"" ^&^& python ""%GATEWAY%""
    )
    call :wait_for_url "%GATEWAY_URL%" 30
    if errorlevel 1 (
        echo ERROR: Chat gateway did not become healthy.
        exit /b 1
    )
)

exit /b 0

:open_vscode
where code.cmd >nul 2>&1
if not errorlevel 1 (
    start "" code.cmd "%WORKSPACE%"
    exit /b 0
)

if exist "%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd" (
    start "" "%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd" "%WORKSPACE%"
    exit /b 0
)
if exist "%ProgramFiles%\Microsoft VS Code\bin\code.cmd" (
    start "" "%ProgramFiles%\Microsoft VS Code\bin\code.cmd" "%WORKSPACE%"
    exit /b 0
)

echo ERROR: VS Code code.cmd was not found.
exit /b 1

:check_model
set "MODEL=%~1"
ollama show "%MODEL%" >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama model %MODEL% is not installed. No pull was attempted.
    exit /b 1
)
exit /b 0

:startup_error
echo.
echo Startup failed. Review the error above.
pause
exit /b 1

:wait_for_url
set "URL=%~1"
set /a ATTEMPTS=%~2
:wait_loop
curl.exe --silent --show-error --fail --max-time 5 "%URL%" >nul 2>&1
if not errorlevel 1 exit /b 0
set /a ATTEMPTS-=1
if %ATTEMPTS% LEQ 0 exit /b 1
timeout /t 1 /nobreak >nul
goto wait_loop