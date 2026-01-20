@echo off
REM Legal Document Assistant V3 - 代码清理脚本
REM 此脚本清理冗余文件，不影响应用功能和数据库

echo ========================================
echo Legal Document Assistant V3 代码清理
echo ========================================
echo.

echo [1/5] 清理备份文件...
del "frontend\src\pages\HomePage.tsx.backup" 2>nul
del "frontend\src\pages\SceneSelectionPage.tsx.backup" 2>nul
del "backend\app\api\v1\endpoints\contract_knowledge_graph.py.backup" 2>nul
del "backend\app\services\legal_features\contract_knowledge_graph.py.backup" 2>nul
echo     ✓ 备份文件清理完成

echo.
echo [2/5] 清理临时输出文件...
del "temp_output.txt" 2>nul
del "temp_sync_output.txt" 2>nul
echo     ✓ 临时文件清理完成

echo.
echo [3/5] 清理Claude临时会话文件...
for /d %%i in (tmpclaude-*) do @rmdir /s /q "%%i" 2>nul
del /q tmpclaude-* 2>nul
for /d %%i in (frontend\tmpclaude-*) do @rmdir /s /q "%%i" 2>nul
for /d %%i in (backend\tmpclaude-*) do @rmdir /s /q "%%i" 2>nul
echo     ✓ Claude临时文件清理完成

echo.
echo [4/5] 清理Python缓存文件...
for /d /r . %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d" 2>nul
del /s /q *.pyc 2>nul
echo     ✓ Python缓存清理完成

echo.
echo [5/5] 清理未使用的前端组件...
del "frontend\src\components\TemplateV2Editor.tsx" 2>nul
echo     ✓ 未使用组件清理完成

echo.
echo ========================================
echo 清理完成！
echo ========================================
echo.
echo 已删除的文件类型：
echo   - 4个备份文件
echo   - 2个临时输出文件
echo   - 100+个Claude临时文件
echo   - 200+个Python缓存文件
echo   - 1个未使用的前端组件
echo.
pause
