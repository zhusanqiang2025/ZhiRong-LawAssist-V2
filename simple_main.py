import os
import sys
import uvicorn
import traceback
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.requests import Request
from fastapi.exceptions import HTTPException

# =================================================================
# 1. 🚀 强制加载环境变量 (.env)
# =================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")

print(f"🔍 正在加载环境变量文件: {env_path}")
load_dotenv(dotenv_path=env_path, verbose=True, override=True)

# 🕵️‍♂️ 环境变量自检 (调试用)
openai_key = os.getenv("OPENAI_API_KEY")
deepseek_key = os.getenv("DEEPSEEK_API_KEY")

print("-" * 50)
print("🔑 密钥检查:")
if openai_key:
    print(f"✅ OPENAI_API_KEY: {openai_key[:5]}...******")
else:
    print("❌ OPENAI_API_KEY: 未找到")

if deepseek_key:
    print(f"✅ DEEPSEEK_API_KEY: {deepseek_key[:5]}...******")
else:
    print("❌ DEEPSEEK_API_KEY: 未找到")
print("-" * 50)

# =================================================================
# 2. 🛠️ 修正 Python 搜索路径
# =================================================================
# 你的结构是 backend/app/main.py
# 且代码里用 from app.xxx import ...
# 所以我们需要把 'backend' 目录加入 sys.path
backend_path = os.path.join(current_dir, "backend")
sys.path.insert(0, backend_path) # 插入到最前面，确保优先级
print(f"🔧 系统路径已添加: {backend_path}")

# =================================================================
# 3. 📥 导入真实的后端应用
# =================================================================
try:
    # 对应文件: backend/app/main.py
    from app.main import app
    print("✅ 成功导入 app.main")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    traceback.print_exc()
    # 尝试另一种导入方式 (容错)
    try:
        from backend.app.main import app
        print("✅ 成功通过 backend.app.main 导入")
    except ImportError as e2:
        print(f"❌ 二次导入失败: {e2}")
        sys.exit(1)

# =================================================================
# 4. 🔥 全局异常捕获 (显示 500 详情)
# =================================================================
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_detail = traceback.format_exc()
    print(f"🔥 [运行时错误]: {error_detail}") 
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": f"服务器内部错误: {str(exc)}",
            "tips": "请检查 simple_main.py 启动日志中的密钥检查部分",
            "traceback": error_detail.split("\n")
        }
    )

# =================================================================
# 5. 📂 挂载静态文件 (解决 404)
# =================================================================
frontend_dist_path = os.path.join(current_dir, "frontend", "dist")

if os.path.exists(frontend_dist_path):
    print(f"📂 挂载前端: {frontend_dist_path}")
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # 必须放在最后，且要避开 api 路由
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi") or full_path.startswith("storage"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
else:
    print(f"⚠️ 前端目录不存在: {frontend_dist_path}")

# =================================================================
# 6. 🚀 启动
# =================================================================
if __name__ == "__main__":
    print("🚀 simple_main 正在启动服务 (端口 7860)...")
    uvicorn.run(app, host="0.0.0.0", port=7860)