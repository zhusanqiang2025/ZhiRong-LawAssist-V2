@echo off
echo ========================================
echo   快速更新前端（直接复制本地构建）
echo ========================================
echo.

echo [1/3] 本地构建前端...
cd frontend
call npm run build
if errorlevel 1 (
    echo.
    echo 构建失败！
    pause
    exit /b 1
)
cd ..

echo [2/3] 复制到容器...
docker cp frontend/dist/. legal_assistant_v3_frontend:/usr/share/nginx/html/

echo [3/3] 验证更新...
docker exec legal_assistant_v3_frontend sh -c "ls -lh /usr/share/nginx/html/assets/index-*.js"

echo.
echo ========================================
echo   更新完成！
echo ========================================
echo.
echo 请在浏览器中按 Ctrl+Shift+R 强制刷新
echo.
pause
