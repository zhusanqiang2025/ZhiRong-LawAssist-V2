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
# 1. 🚀 强制加载环境变量
# =================================================================
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")

# 尝试加载
load_dotenv(dotenv_path=env_path, verbose=True, override=True)

# =================================================================
# 2. 🛠️ 修正 Python 搜索路径
# =================================================================
backend_path = os.path.join(current_dir, "backend")
sys.path.insert(0, backend_path)

# =================================================================
# 3. 📥 导入后端应用
# =================================================================
try:
    from app.main import app
    print("✅ 成功导入 app.main")
except ImportError as e:
    print(f"❌ 导入失败: {e}")
    # 紧急创建一个临时 app 用于报错
    from fastapi import FastAPI
    app = FastAPI()

# =================================================================
# 🕵️‍♂️ 新增：环境调试接口 (部署后访问这个接口查看真相)
# =================================================================
@app.get("/api/debug/env-check")
async def debug_env_check():
    """
    这个接口用于诊断为什么读不到 API Key
    """
    # 1. 检查文件是否存在
    file_exists = os.path.exists(env_path)
    file_size = os.path.getsize(env_path) if file_exists else 0
    
    # 2. 读取文件前几行 (脱敏)
    file_preview = []
    if file_exists:
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in lines:
                    key = line.split("=")[0].strip()
                    if key:
                        file_preview.append(f"{key}=****** (长度: {len(line)})")
        except Exception as e:
            file_preview.append(f"读取失败: {str(e)}")

    # 3. 检查实际环境变量
    openai_key = os.getenv("OPENAI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    return {
        "status": "debug",
        "file_check": {
            "path": env_path,
            "exists": file_exists,
            "size_bytes": file_size,
            "content_preview": file_preview
        },
        "env_vars_in_memory": {
            "OPENAI_API_KEY": "✅ 已加载" if openai_key else "❌ 未找到 (None)",
            "DEEPSEEK_API_KEY": "✅ 已加载" if deepseek_key else "❌ 未找到 (None)",
            "Current_Dir": current_dir,
            "Dir_Files": os.listdir(current_dir) # 看看根目录下到底有啥
        }
    }

# =================================================================
# 4. 🔥 全局异常捕获
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
            "tips": "请访问 /api/debug/env-check 接口查看环境变量状态",
            "timestamp": str(os.times())
        }
    )

# =================================================================
# 5. 📂 挂载静态文件
# =================================================================
frontend_dist_path = os.path.join(current_dir, "frontend", "dist")
if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("storage"):
            raise HTTPException(status_code=404, detail="Not Found")
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

# =================================================================
# 6. 🚀 启动
# =================================================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)