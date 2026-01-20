@echo off
echo 正在构建Legal Document Assistant后端Docker镜像...

REM 切换到当前目录
cd /d "%~dp0"

REM 构建Docker镜像
docker build -t legal-assistant-backend .

if %ERRORLEVEL% == 0 (
    echo.
    echo Docker镜像构建成功！
    echo 您可以使用以下命令运行容器：
    echo docker run -p 8000:8000 legal-assistant-backend
) else (
    echo.
    echo Docker镜像构建失败，请检查错误信息。
)

pause