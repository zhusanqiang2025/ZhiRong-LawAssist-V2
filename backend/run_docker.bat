@echo off
echo 正在启动Legal Document Assistant后端Docker容器...

REM 切换到当前目录
cd /d "%~dp0"

REM 运行Docker容器
docker run -p 8000:8000 --name legal-assistant legal-assistant-backend

if %ERRORLEVEL% == 0 (
    echo.
    echo Docker容器已启动！
    echo 服务将在 http://localhost:8000 可用
) else (
    echo.
    echo Docker容器启动失败，请检查错误信息。
)

pause