@echo off
setlocal enabledelayedexpansion

REM ========================================
REM 前端Docker镜像自动重新构建脚本
REM ========================================

echo.
echo ========================================
echo   前端Docker镜像自动重新构建脚本
echo ========================================
echo.

REM 获取时间戳
for /f "tokens=2 delims==" %%a in ('wmic OS Get localdatetime /value') do set "datetime=%%a"
set "BUILD_VERSION=%datetime:~0,8%%datetime:~8,6%"

echo [1/6] 停止前端容器...
docker-compose stop frontend >nul 2>&1
echo     √ 容器已停止

echo [2/6] 删除前端容器...
docker-compose rm -f frontend >nul 2>&1
echo     √ 容器已删除

echo [3/6] 删除前端镜像...
docker rmi legal_document_assistantv3-frontend >nul 2>&1
echo     √ 镜像已删除

echo [4/6] 清理Docker构建缓存...
docker builder prune -f >nul 2>&1
echo     √ 缓存已清理

echo [5/6] 重新构建前端镜像...
echo     这可能需要几分钟...
docker-compose build --no-cache --build-arg BUILD_VERSION=%BUILD_VERSION% frontend
if errorlevel 1 (
    echo.
    echo ========================================
    echo   错误: 构建失败！
    echo ========================================
    echo.
    pause
    exit /b 1
)
echo     √ 镜像构建完成

echo [6/6] 启动前端容器...
docker-compose up -d frontend >nul 2>&1
timeout /t 3 /nobreak >nul

REM 验证容器状态
docker ps --filter "name=frontend" --format "{{.Status}}" | findstr "Up" >nul
if errorlevel 1 (
    echo     ✗ 容器启动失败
) else (
    echo     √ 容器已启动

    echo.
    echo 验证容器中的文件:
    docker exec legal_assistant_v3_frontend sh -c "ls -lh /usr/share/nginx/html/assets/index-*.js"
)

echo.
echo ========================================
echo   重建完成！
echo ========================================
echo.
echo 请执行以下操作查看更新:
echo   1. 在浏览器中按 Ctrl+Shift+R 强制刷新
echo   2. 或清除浏览器缓存后刷新
echo.
pause
