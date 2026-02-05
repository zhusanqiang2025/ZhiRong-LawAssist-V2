@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM 生成时间戳格式：YYYYMMDD_HHMMSS
set "YEAR=%date:~0,4%"
set "MONTH=%date:~5,2%"
set "DAY=%date:~8,2%"
set "HOUR=%time:~0,2%"
set "MIN=%time:~3,2%"
set "SEC=%time:~6,2%"
set "TIMESTAMP=%YEAR%%MONTH%%DAY%_%HOUR%%MIN%%SEC%"

set "SOURCE_FILE=backend\config\review_rules.json"
set "BACKUP_DIR=backend\config\backup"
set "BACKUP_FILE=%BACKUP_DIR%\review_rules_%TIMESTAMP%.json"

echo ===================================================
echo 后端规则备份工具
echo ===================================================
echo.
echo 当前时间: %TIMESTAMP%
echo.

REM 检查源文件是否存在
if not exist "%SOURCE_FILE%" (
    echo [错误] 规则文件不存在: %SOURCE_FILE%
echo 请检查文件路径是否正确
    pause
    exit /b 1
)

echo [信息] 找到规则文件: %SOURCE_FILE%

REM 创建备份目录
if not exist "%BACKUP_DIR%" (
    mkdir "%BACKUP_DIR%"
    echo [信息] 创建备份目录: %BACKUP_DIR%
)

REM 复制文件
copy "%SOURCE_FILE%" "%BACKUP_FILE%" >nul 2>&1
if errorlevel 1 (
    echo [错误] 备份失败
    pause
    exit /b 1
)

echo.
echo ===================================================
echo [成功] 备份完成
echo ===================================================
echo.
echo 备份文件: %BACKUP_FILE%
echo 原始文件: %SOURCE_FILE%
echo.
echo 您可以安全地修改 review_rules.json 文件
echo 如需恢复，请将备份文件复制回原位置
echo ===================================================
echo.
pause
