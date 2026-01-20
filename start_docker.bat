@echo off
chcp 65001 >nul
title Legal Document Assistant - Docker启动器

echo.
echo ==========================================
echo    Legal Document Assistant - Docker启动
echo ==========================================
echo.

echo 正在检查Docker服务...
docker --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker未安装或未启动
    echo 请先启动Docker Desktop
    pause
    exit /b 1
)

echo ✅ Docker检查通过
echo.

echo 🔄 正在停止现有服务...
docker-compose down

echo.
echo 🧹 清理Docker缓存...
docker system prune -f

echo.
echo 🚀 启动Legal Document Assistant...
echo 注意：首次启动可能需要5-10分钟来下载镜像
echo 如果遇到网络错误，请稍后重试
echo.

docker-compose up --build

pause