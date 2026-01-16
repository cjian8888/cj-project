@echo off
chcp 65001 >nul
echo ========================================
echo   资金穿透审计系统 - 服务停止脚本
echo ========================================
echo.
echo 正在检查8000端口占用情况...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 ^| findstr LISTENING') do (
    echo 发现进程 PID: %%a 占用端口8000
    echo 正在终止进程...
    taskkill /F /PID %%a >nul 2>&1
    if %errorlevel%==0 (
        echo [OK] 进程 %%a 已终止
    ) else (
        echo [WARN] 进程 %%a 终止失败，可能需要管理员权限
    )
)
echo.
echo 正在终止所有Python进程（可选）...
set /p choice="是否终止所有Python进程? (Y/N): "
if /i "%choice%"=="Y" (
    taskkill /F /IM python.exe >nul 2>&1
    echo [OK] 所有Python进程已终止
) else (
    echo [SKIP] 跳过终止Python进程
)
echo.
echo 清理完成！现在可以安全地重启服务了。
echo ========================================
pause
