@echo off
chcp 65001 >nul
setlocal

echo ========================================
echo TrendRadar 远程数据拉取工具
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ 错误: 未找到Python，请先安装Python
    pause
    exit /b 1
)

:: 运行Python脚本
python pull_remote_news.py %*

:: 如果出错则暂停
if %errorlevel% neq 0 (
    echo.
    echo 程序执行出错，按任意键退出...
    pause >nul
)