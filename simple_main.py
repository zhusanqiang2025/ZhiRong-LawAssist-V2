import os
import sys
import uvicorn
import traceback
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse # 👈 新增 JSONResponse
from fastapi.requests import Request # 👈 新增 Request
from fastapi.exceptions import HTTPException

# =================================================================
# 1. 环境准备
# =================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
backend_path = os.path.join(current_dir, "backend")
sys.path.append(backend_path)

# =================================================================
# 2. 导入后端应用
# =================================================================
try:
    from backend.app import app
    print("✅ 成功加载后端核心逻辑")
except ImportError as e:
    print(f"❌ 无法导入后端应用: {e}")
    sys.exit(1)

# =================================================================
# 🚨🚨🚨 新增：全局异常捕获 (这是为了让你在前端看到报错原因) 🚨🚨🚨
# =================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # 获取详细的堆栈跟踪信息
    error_detail = traceback.format_exc()
    print(f"🔥 后端严重错误: {error_detail}") # 打印到服务器日志
    
    # 将错误直接返回给前端 (调试模式)
    return JSONResponse(
        status_code=500,
        content={
            "message": "Internal Server Error",
            "error_type": type(exc).__name__,
            "detail": str(exc),
            "traceback": error_detail.split("\n") # 把堆栈切分成数组方便阅读
        }
    )

# =================================================================
# 3. 挂载静态文件
# =================================================================
frontend_dist_path = os.path.join(current_dir, "frontend", "dist")

if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="API Not Found")
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
else:
    print(f"⚠️ 警告: 未找到前端 dist 目录")

# =================================================================
# 4. 启动服务
# =================================================================
if __name__ == "__main__":
    print("🚀 服务启动在端口 7860...")
    uvicorn.run(app, host="0.0.0.0", port=7860)