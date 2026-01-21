import os
import sys
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.exceptions import HTTPException

# =================================================================
# 1. 环境准备：让 Python 能找到 backend 目录下的模块
# =================================================================
# 获取当前 simple_main.py 所在的目录 (项目根目录)
current_dir = os.path.dirname(os.path.abspath(__file__))
# 拼接 backend 路径
backend_path = os.path.join(current_dir, "backend")
# 将 backend 加入 Python 搜索路径，这样 import contract_review_graph 才能工作
sys.path.append(backend_path)

print(f"🔧 系统路径已添加: {backend_path}")

# =================================================================
# 2. 导入真实的后端应用
# =================================================================
try:
    # 从 backend/app.py 中导入 app 对象
    from backend.app import app
    print("✅ 成功加载后端核心逻辑 (backend/app.py)")
except ImportError as e:
    print("❌ 致命错误：无法导入后端应用")
    print(f"详细错误: {e}")
    # 如果这里报错，说明 backend 下缺少 __init__.py 或者依赖没装好
    sys.exit(1)

# =================================================================
# 3. 挂载前端静态文件 (解决 404 问题)
# =================================================================
# 前端构建产物路径: E:\legal_document_assistant v3\frontend\dist
frontend_dist_path = os.path.join(current_dir, "frontend", "dist")

if os.path.exists(frontend_dist_path):
    print(f"📂 发现前端资源目录: {frontend_dist_path}")
    
    # 1. 挂载静态资源 (JS/CSS/图片) -> /assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # 2. 全局路由捕获 (处理 SPA 刷新和首页访问)
    # 注意：这个必须放在所有 API 路由定义之后，而由于我们是导入了 app，API 路由已经定义好了
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        # 排除 API 请求、文档请求
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="API Not Found")
        
        # 其他所有路径都返回 index.html
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))
    
    print("✅ 前端静态托管已配置")
else:
    print(f"⚠️ 警告: 未找到前端 dist 目录: {frontend_dist_path}")
    print("👉 请确保在 frontend 目录下执行了 'npm run build'")

# =================================================================
# 4. 启动服务
# =================================================================
if __name__ == "__main__":
    # 使用 Dockerfile 中暴露的 7860 端口
    print("🚀 服务正在启动，端口: 7860")
    uvicorn.run(app, host="0.0.0.0", port=7860)