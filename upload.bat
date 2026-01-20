@echo off
REM ========================================
REM 文件上传脚本 - Windows 版本
REM ========================================
REM 使用方法：
REM 1. 修改下方配置
REM 2. 双击运行此文件
REM 3. 需要 pscp.exe (PuTTY) 或 Git Bash
REM ========================================

setlocal enabledelayedexpansion

REM ========================================
REM 配置区域 - 请修改为您的实际信息
REM ========================================

set SERVER_USER=root
set SERVER_HOST=YOUR_SERVER_IP
set SERVER_PATH=~/legal-assistant

REM ========================================

echo =========================================
echo 法律文档助手 - 文件上传工具
echo =========================================
echo.
echo 目标服务器: %SERVER_USER%@%SERVER_HOST%
echo 目标路径:   %SERVER_PATH%
echo.

REM 检查 pscp 是否可用
where pscp >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误: pscp 命令不可用
    echo.
    echo 请选择以下方式之一：
    echo 1. 安装 PuTTY (包含 pscp)
    echo 2. 使用 Git Bash 运行 upload.sh
    echo 3. 使用 Termius 的 SFTP 功能
    echo 4. 使用 WinSCP 图形界面
    pause
    exit /b 1
)

set /p confirm="是否开始上传？ (y/N): "
if /i not "%confirm%"=="y" (
    echo 已取消
    pause
    exit /b 0
)

REM 创建远程目录
echo 创建远程目录...
plink -batch %SERVER_USER%@%SERVER_HOST% "mkdir -p %SERVER_PATH%/storage/uploads %SERVER_PATH%/storage/chroma_db"

if %errorlevel% neq 0 (
    echo 错误: 无法连接到服务器
    echo 请检查 pscp 和 plink 是否在 PATH 中
    pause
    exit /b 1
)

REM 上传文件
echo 上传文件...
echo   [1/6] docker-compose.yml
pscp docker-compose.yml %SERVER_USER%@%SERVER_HOST%:%SERVER_PATH%/

echo   [2/6] .env
pscp .env %SERVER_USER%@%SERVER_HOST%:%SERVER_PATH%/

echo   [3/6] backend/
pscp -r backend\ %SERVER_USER%@%SERVER_HOST%:%SERVER_PATH%/

echo   [4/6] frontend/
pscp -r frontend\ %SERVER_USER%@%SERVER_HOST%:%SERVER_PATH%/

echo   [5/6] deploy.sh
pscp deploy.sh %SERVER_USER%@%SERVER_HOST%:%SERVER_PATH%/

echo   [6/6] 添加执行权限
plink -batch %SERVER_USER%@%SERVER_HOST% "chmod +x %SERVER_PATH%/deploy.sh"

echo.
echo =========================================
echo 文件上传完成！
echo =========================================
echo.
echo 下一步操作：
echo 1. 使用 Termius 或 PuTTY 登录服务器
echo 2. 进入项目目录:   cd %SERVER_PATH%
echo 3. 编辑配置文件:   nano .env
echo 4. 运行部署脚本:   bash deploy.sh
echo.
pause
