@echo off
chcp 65001 >nul
title Legal Document Assistant - 本地Python启动器

echo.
echo ==========================================
echo    Legal Document Assistant - 本地启动
echo ==========================================
echo.

REM 检查Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未找到Python
    echo.
    echo 请从 https://python.org 下载并安装Python 3.10+
    echo 安装时请勾选 "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo ✅ Python环境检查通过
echo.

REM 启动Python脚本
echo 🚀 正在启动Python启动器...
echo.
python start_local.py

pause