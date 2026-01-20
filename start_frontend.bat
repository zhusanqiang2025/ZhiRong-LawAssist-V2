@echo off
chcp 65001 >nul
echo ==========================================
echo    启动 Legal Document Assistant 前端
echo ==========================================
echo.

echo 启动前端容器...
docker start legal_assistant_v3_frontend

if errorlevel 1 (
    echo 容器启动失败，尝试创建并启动...
    docker-compose up -d frontend
) else (
    echo 前端容器已启动
)

echo.
echo 前端地址: http://localhost:3000
echo.
echo 按任意键退出...
pause >nul
