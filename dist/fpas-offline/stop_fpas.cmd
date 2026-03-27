@echo off
setlocal
cd /d "%~dp0"
set "FPAS_ROOT=%~dp0"
if "%FPAS_ROOT:~-1%"=="\" set "FPAS_ROOT=%FPAS_ROOT:~0,-1%"
set "FPAS_PYTHON=%FPAS_ROOT%\runtime\python\python.exe"
set "FPAS_STOP_HELPER=%FPAS_ROOT%\stop_fpas_helper.py"
set "FPAS_RUN_DIR=%FPAS_ROOT%\run"
if not exist "%FPAS_PYTHON%" (
echo [FPAS] 缺少内置 Python 运行时: "%FPAS_PYTHON%"
pause
exit /b 1
)
if not exist "%FPAS_STOP_HELPER%" (
echo [FPAS] 缺少停止脚本: "%FPAS_STOP_HELPER%"
pause
exit /b 1
)
"%FPAS_PYTHON%" "%FPAS_STOP_HELPER%"
set "EXIT_CODE=%ERRORLEVEL%"
del /f /q "%FPAS_RUN_DIR%\server.pid" >nul 2>nul
del /f /q "%FPAS_RUN_DIR%\browser.pid" >nul 2>nul
del /f /q "%FPAS_RUN_DIR%\stopping.flag" >nul 2>nul
if not "%EXIT_CODE%"=="0" (
echo.
echo [FPAS] 停止脚本执行失败，退出码=%EXIT_CODE%
pause
)
exit /b %EXIT_CODE%
