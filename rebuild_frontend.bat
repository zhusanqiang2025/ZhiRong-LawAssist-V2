@echo off
chcp 65001 >nul
echo ==========================================
echo  重新构建前端 Docker 镜像
echo ==========================================
echo.

echo 停止并删除旧的前端容器...
docker-compose rm -f frontend
echo.

echo 重新构建前端镜像...
docker-compose build frontend

echo.
echo 构建完成！
echo.
echo 启动所有容器...
docker-compose up -d

echo.
echo 前端地址: http://localhost:3000
echo 后端地址: http://localhost:8000
echo.
pause
