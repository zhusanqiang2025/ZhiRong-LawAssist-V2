import os
import sys
import uvicorn
import traceback
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.requests import Request
from fastapi.exceptions import HTTPException

# =================================================================
# 1. ✅ [关键修改] 优先加载环境变量 (.env)
# =================================================================
# 必须在导入 backend.app 之前执行，否则后端初始化时读不到 Key
from dotenv import load_dotenv

# 获取当前目录
current_dir = os.path.dirname(os.path.abspath(__file__))

# 加载 .env 文件 (override=True 表示覆盖系统原有变量，确保使用最新配置)
env_path = os.path.join(current_dir, ".env")
load_dotenv(dotenv_path=env_path, verbose=True, override=True)

print(f"🔧 环境变量加载完成，路径: {env_path}")

# =================================================================
# 2. 环境准备：添加后端路径
# =================================================================
backend_path = os.path.join(current_dir, "backend")
sys.path.append(backend_path)

# =================================================================
# 3. 导入后端应用
# =================================================================
try:
    from backend.app import app
    print("✅ 成功加载后端核心逻辑")
except ImportError as e:
    print(f"❌ 无法导入后端应用: {e}")
    # 打印详细错误堆栈，方便排查 import 错误
    traceback.print_exc()
    sys.exit(1)

# =================================================================
# 4. 全局异常捕获 (将后端 500 错误直接显示在前端，方便调试)
# =================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = traceback.format_exc()
    print(f"🔥 后端严重错误: {error_detail}") 
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"服务器内部错误: {str(exc)}",
            "code": "INTERNAL_SERVER_ERROR",
            "traceback": error_detail.split("\n")
        }
    )

# =================================================================
# 5. 挂载前端静态文件 (解决 404 问题)
# =================================================================
frontend_dist_path = os.path.join(current_dir, "frontend", "dist")

if os.path.exists(frontend_dist_path):
    print(f"📂 发现前端资源目录: {frontend_dist_path}")
    
    # 挂载静态资源
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # 处理 SPA 路由
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):