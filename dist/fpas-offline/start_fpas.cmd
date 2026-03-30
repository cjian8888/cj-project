@echo off
setlocal
cd /d "%~dp0"
set "FPAS_ROOT=%~dp0"
if "%FPAS_ROOT:~-1%"=="\" set "FPAS_ROOT=%FPAS_ROOT:~0,-1%"
set "FPAS_RUN_DIR=%FPAS_ROOT%\run"
if not exist "%FPAS_RUN_DIR%" mkdir "%FPAS_RUN_DIR%" >nul 2>nul
set "FPAS_SERVER_PID_FILE=%FPAS_RUN_DIR%\server.pid"
set "FPAS_BROWSER_PID_FILE=%FPAS_RUN_DIR%\browser.pid"
set "FPAS_BROWSER_PROFILE_DIR=%FPAS_RUN_DIR%\browser-profile"
set "FPAS_STOPPING_FLAG=%FPAS_RUN_DIR%\stopping.flag"
del /f /q "%FPAS_SERVER_PID_FILE%" >nul 2>nul
del /f /q "%FPAS_BROWSER_PID_FILE%" >nul 2>nul
del /f /q "%FPAS_STOPPING_FLAG%" >nul 2>nul
set "FPAS_DELIVERY_MODE=1"
if not defined FPAS_AUTO_OPEN_BROWSER set "FPAS_AUTO_OPEN_BROWSER=1"
set "FPAS_PYTHON=%FPAS_ROOT%\runtime\python\python.exe"
if not exist "%FPAS_PYTHON%" (
echo [FPAS] 缺少内置 Python 运行时: "%FPAS_PYTHON%"
pause
exit /b 1
)
set "FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_ROOT%"
set "PYTHONPATH=%FPAS_ROOT%"
set "PATH=%FPAS_ROOT%\runtime\python;%FPAS_ROOT%\runtime\python\DLLs;%FPAS_ROOT%\runtime\python\Scripts;%PATH%"
if not defined FPAS_PORT set "FPAS_PORT=8000"
start "" /b cmd /c "set FPAS_ROOT=%FPAS_ROOT% && set FPAS_RUN_DIR=%FPAS_RUN_DIR% && set FPAS_SERVER_PID_FILE=%FPAS_SERVER_PID_FILE% && set FPAS_BROWSER_PID_FILE=%FPAS_BROWSER_PID_FILE% && set FPAS_BROWSER_PROFILE_DIR=%FPAS_BROWSER_PROFILE_DIR% && set FPAS_STOPPING_FLAG=%FPAS_STOPPING_FLAG% && set FPAS_DELIVERY_MODE=%FPAS_DELIVERY_MODE% && set FPAS_AUTO_OPEN_BROWSER=%FPAS_AUTO_OPEN_BROWSER% && set FPAS_PORT=%FPAS_PORT% && set FPAS_STARTUP_DIAGNOSTICS_ROOT=%FPAS_STARTUP_DIAGNOSTICS_ROOT% && set PYTHONPATH=%PYTHONPATH% && set PATH=%PATH% && "%FPAS_PYTHON%" "%FPAS_ROOT%\launch_browser_helper.py"
"%FPAS_PYTHON%" "%FPAS_ROOT%\api_server.py"
set "EXIT_CODE=%ERRORLEVEL%"
del /f /q "%FPAS_SERVER_PID_FILE%" >nul 2>nul
del /f /q "%FPAS_BROWSER_PID_FILE%" >nul 2>nul
if exist "%FPAS_STOPPING_FLAG%" (
del /f /q "%FPAS_STOPPING_FLAG%" >nul 2>nul
) else (
if not "%EXIT_CODE%"=="0" (
echo.
echo [FPAS] 服务异常退出，退出码=%EXIT_CODE%
pause
)
)
exit /b %EXIT_CODE%
