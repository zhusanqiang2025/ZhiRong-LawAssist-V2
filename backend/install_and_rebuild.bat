@echo off
cd /d "%~dp0"
echo =================================================
echo 合同模板向量索引重建脚本
echo =================================================
echo.

echo [1/3] 检查虚拟环境...
if exist ".venv\Scripts\activate.bat" (
    echo 找到虚拟环境，正在激活...
    call .venv\Scripts\activate.bat
) else (
    echo 未找到虚拟环境，使用系统 Python
)

echo.
echo [2/3] 安装/更新依赖包...
pip install -r requirements.txt

echo.
echo [3/3] 重建向量索引...
python rebuild_vector_index.py

echo.
echo =================================================
echo 完成！
echo =================================================
pause
