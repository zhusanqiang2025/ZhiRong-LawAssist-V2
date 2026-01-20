@echo off
chcp 65001 >nul
echo 检查Docker容器状态...
echo.

echo 检查后端容器...
docker ps -a | findstr backend
echo.

echo 如果后端容器未运行，尝试启动...
docker start legal_assistant_v3_backend 2>nul
if errorlevel 1 (
    echo 容器启动失败，尝试重新创建...
    docker-compose up -d backend
) else (
    echo 后端容器已启动
)

echo.
echo 等待5秒让服务完全启动...
timeout /t 5 /nobreak >nul

echo.
echo 测试后端API...
curl -s http://localhost:8000/api/v1/health || echo API不可访问

echo.
echo 按任意键退出...
pause >nul
