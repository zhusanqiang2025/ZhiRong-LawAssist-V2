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
# 1. 🚀 强制加载环境变量 (从 Dockerfile 配置读取，无需 .env 文件)
# =================================================================
def _load_env_from_dockerfile():
    """
    从 backend/Dockerfile 读取环境变量配置
    这样就不需要 .env 文件了，配置统一在 Dockerfile 管理
    """
    env_config = {
        # ==================== 环境配置 ====================
        "ENVIRONMENT": "development",
        "DEFAULT_ADMIN_PASSWORD": "admin123",

        # ==================== Redis 配置 ====================
        "REDIS_HOST": "redis7.gms.svc.cluster.local",
        "REDIS_PORT": "6379",
        "REDIS_DB": "0",
        "REDIS_URL": "redis://redis7.gms.svc.cluster.local:6379/0",

        # ==================== PostgreSQL 数据库配置 ====================
        "POSTGRES_SERVER": "postgres18-0.postgres18.gms.svc.cluster.local",
        "POSTGRES_PORT": "5432",
        "POSTGRES_DB": "legal_assistant_db",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "postgres",
        "DATABASE_URL": "postgresql://postgres:postgres@postgres18-0.postgres18.gms.svc.cluster.local:5432/legal_assistant_db",

        # ==================== 应用密钥配置 ====================
        "SECRET_KEY": "a_very_long_and_super_secret_random_string_that_is_hard_to_guess",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "1440",

        # ==================== ONLYOFFICE 配置 ====================
        "ONLYOFFICE_JWT_SECRET": "legal_doc_secret_2025",
        "BACKEND_PUBLIC_URL": "http://localhost:8000",

        # ==================== Dify 配置 (暂时禁用) ====================
        "DIFY_ENABLED": "false",
        "DIFY_GUIDANCE_ANALYSIS_ENABLED": "false",
        "DIFY_EXPERT_CONSULTATION_ENABLED": "false",

        # ==================== DeepSeek API 配置 ====================
        "DEEPSEEK_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
        "DEEPSEEK_API_URL": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",
        "DEEPSEEK_MODEL": "deepseek-chat",
        "DEEPSEEK_TEMPERATURE": "0.7",
        "DEEPSEEK_MAX_TOKENS": "2000",
        "DEEPSEEK_TIMEOUT": "60",

        # ==================== LangChain API 配置 (风险评估等核心功能) ====================
        "LANGCHAIN_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
        "LANGCHAIN_API_BASE_URL": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",
        "MODEL_NAME": "Qwen3-235B-A22B-Thinking-2507",

        # ==================== OpenAI API 配置 (合同生成模块) ====================
        "OPENAI_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
        "OPENAI_API_BASE": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",

        # ==================== MinerU PDF 解析服务配置 ====================
        "MINERU_API_URL": "http://115.190.40.198:7231/v2/parse/file",
        "MINERU_API_TIMEOUT": "120",
        "MINERU_ENABLED": "true",

        # ==================== OCR 服务配置 ====================
        "OCR_API_URL": "http://115.190.43.141:8002/ocr/v1/recognize-text",
        "OCR_API_TIMEOUT": "60",
        "OCR_ENABLED": "true",

        # ==================== AI 文档预处理配置 ====================
        "AI_POSTPROCESS_ENABLED": "true",
        "AI_POSTPROCESS_MODEL": "qwen3-vl:32b-thinking-q8_0",
        "AI_POSTPROCESS_API_URL": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",
        "AI_POSTPROCESS_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
        "AI_AUTH_TYPE": "bearer",
        "AI_POSTPROCESS_TIMEOUT": "30",
        "AI_POSTPROCESS_BATCH_SIZE": "5",
        "AI_POSTPROCESS_CONFIDENCE_THRESHOLD": "0.7",
        "AI_POSTPROCESS_ONLY_AMBIGUOUS": "true",

        # ==================== Qwen3-235B-A22B-Thinking-2507 模型配置 ====================
        "QWEN3_THINKING_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
        "QWEN3_THINKING_API_URL": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",
        "QWEN3_THINKING_MODEL": "Qwen3-235B-A22B-Thinking-2507",
        "QWEN3_THINKING_TIMEOUT": "120",
        "QWEN3_THINKING_ENABLED": "true",

        # ==================== GPT-OSS-120B 模型配置 ====================
        "GPT_OSS_120B_API_URL": "http://101.126.134.56:11434/v1",
        "GPT_OSS_120B_MODEL": "gpt-oss:120b",

        # ==================== BGE 嵌入模型配置 (向量检索) ====================
        "BGE_EMBEDDING_API_URL": "http://115.190.43.141:11434/api/embed",
        "BGE_RERANKER_API_URL": "http://115.190.43.141:9997/v1/rerank",
        "BGE_MODEL_NAME": "bge-m3",
        "BGE_EMBEDDING_DIM": "1024",
        "BGE_TIMEOUT": "30",

        # ==================== Celery 任务队列配置 ====================
        "CELERY_BROKER_URL": "redis://redis:6379/0",
        "CELERY_RESULT_BACKEND": "redis://redis:6379/0",
        "CELERY_ENABLED": "true",
        "CELERY_TASK_TRACK_STARTED": "true",
        "CELERY_TASK_TIME_LIMIT": "3600",
        "CELERY_TASK_SOFT_TIME_LIMIT": "3300",

        # ==================== Flower 监控配置 ====================
        "FLOWER_PORT": "5556",

        # ==================== 向量数据库配置 ====================
        "CHROMA_PERSIST_DIR": "./storage/chroma_db",
        "VECTOR_DB_TYPE": "chroma",
    }

    # 设置环境变量到 os.environ
    for key, value in env_config.items():
        os.environ[key] = value

    print(f"✅ 已从 Dockerfile 配置加载 {len(env_config)} 个环境变量")

# 执行环境变量加载
_load_env_from_dockerfile()

# 🔍 调试：打印关键环境变量（用于排查问题）
print("=" * 60)
print("[调试] 关键环境变量检查:")
print(f"  OPENAI_API_KEY: {'✅ 已设置' if os.getenv('OPENAI_API_KEY') else '❌ 未设置'}")
print(f"  DEEPSEEK_API_KEY: {'✅ 已设置' if os.getenv('DEEPSEEK_API_KEY') else '❌ 未设置'}")
print(f"  LANGCHAIN_API_KEY: {'✅ 已设置' if os.getenv('LANGCHAIN_API_KEY') else '❌ 未设置'}")
print(f"  QWEN3_THINKING_API_KEY: {'✅ 已设置' if os.getenv('QWEN3_THINKING_API_KEY') else '❌ 未设置'}")
print("=" * 60)

# 额外：也尝试加载 .env 文件（如果存在，可以覆盖 Dockerfile 配置）
current_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(current_dir, ".env")
from dotenv import load_dotenv
load_dotenv(dotenv_path=env_path, verbose=True, override=False)  # 不覆盖已设置的值

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
# 🕵️‍♂️ 环境调试接口 (访问这个接口查看配置状态)
# =================================================================
@app.get("/api/v1/debug/env-check")
async def debug_env_check():
    """
    诊断环境变量是否正确加载
    """
    return {
        "status": "debug",
        "env_source": "从 Dockerfile 配置加载（无需 .env 文件）",
        "critical_vars": {
            "OPENAI_API_KEY": f"✅ 已配置 (长度: {len(os.getenv('OPENAI_API_KEY', ''))})" if os.getenv("OPENAI_API_KEY") else "❌ 未配置",
            "LANGCHAIN_API_KEY": f"✅ 已配置 (长度: {len(os.getenv('LANGCHAIN_API_KEY', ''))})" if os.getenv("LANGCHAIN_API_KEY") else "❌ 未配置",
            "DEEPSEEK_API_KEY": f"✅ 已配置 (长度: {len(os.getenv('DEEPSEEK_API_KEY', ''))})" if os.getenv("DEEPSEEK_API_KEY") else "❌ 未配置",
            "QWEN3_THINKING_API_KEY": f"✅ 已配置 (长度: {len(os.getenv('QWEN3_THINKING_API_KEY', ''))})" if os.getenv("QWEN3_THINKING_API_KEY") else "❌ 未配置",
            "DATABASE_URL": f"✅ {os.getenv('DATABASE_URL', '')[:50]}..." if os.getenv("DATABASE_URL") else "❌ 未配置",
            "REDIS_URL": f"✅ 已配置" if os.getenv("REDIS_URL") else "❌ 未配置",
        },
        "all_env_vars_count": len(os.environ),
        "current_dir": current_dir,
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
            "tips": "请访问 /api/v1/debug/env-check 接口查看环境变量状态",
            "timestamp": str(os.times())
        }
    )

# =================================================================
# 5. 📂 挂载静态文件 (前端构建产物)
# =================================================================
frontend_dist_path = os.path.join(current_dir, "frontend", "dist")
if os.path.exists(frontend_dist_path):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    @app.get("/{full_path:path}")
    async def catch_all(full_path: str):
        # 排除 API 路由、静态资源、文档等路径
        excluded_prefixes = ("api", "docs", "redoc", "storage", "health", "openapi")
        if full_path.startswith(excluded_prefixes):
            raise HTTPException(status_code=404, detail="Not Found")
        index_file = os.path.join(frontend_dist_path, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        raise HTTPException(status_code=404, detail="Frontend not built")

# =================================================================
# 6. 🚀 启动
# =================================================================
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)