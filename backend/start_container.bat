@echo off
echo 正在启动Legal Document Assistant后端容器...

REM 切换到当前目录
cd /d "%~dp0"

echo 停止已存在的容器（如果存在）
docker stop legal-assistant 2>nul

echo 启动新的容器
docker run -d -p 8000:8000 --name legal-assistant legal-assistant-backend

if %ERRORLEVEL% == 0 (
    echo.
    echo Docker容器已启动！
    echo 服务将在 http://localhost:8000 可用
    echo API文档: http://localhost:8000/docs
    echo.
    echo 等待服务启动...
    timeout /t 10 /nobreak >nul
    echo.
    echo 检查服务状态...
    powershell -Command "Invoke-RestMethod -Uri http://localhost:8000/health -Method Get"
) else (
    echo.
    echo Docker容器启动失败，请检查错误信息。
)

echo.
echo 您可以使用以下命令查看容器日志：
echo docker logs legal-assistant
echo.
echo 按任意键查看容器日志...
pause
docker logs legal-assistant