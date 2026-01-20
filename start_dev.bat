@echo off
echo ========================================
echo 法律文书助手 - 本地开发模式启动脚本
echo ========================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10 或更高版本
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Node.js，请先安装 Node.js
    pause
    exit /b 1
)

REM 启动后端
echo [1/2] 启动后端服务...
cd backend
start "后端服务" cmd /k "python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"
cd ..

REM 等待后端启动
timeout /t 5 /nobreak >nul

REM 启动前端
echo [2/2] 启动前端服务...
cd frontend
start "前端服务" cmd /k "npm run dev"
cd ..

echo.
echo ========================================
echo 服务启动完成！
echo ========================================
echo 前端地址: http://localhost:5173
echo 后端API: http://localhost:8000
echo API文档: http://localhost:8000/docs
echo ========================================
echo.
echo 提示：服务窗口会保持打开，关闭窗口将停止对应服务
pause