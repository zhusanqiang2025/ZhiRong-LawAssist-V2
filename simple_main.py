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

    【修复】优先使用已存在的环境变量（Dockerfile ENV 配置）
    只有在环境变量未设置时，才使用这里的默认值
    """
    # 默认配置（仅在环境变量未设置时使用）
    default_config = {
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
        "DEEPSEEK_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",  # 本地开发默认值，生产环境会被 Dockerfile ENV 覆盖
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
    # 【修复】优先使用已存在的环境变量（Dockerfile ENV 配置）
    # 只有在环境变量未设置时，才使用这里的默认值
    set_count = 0
    for key, value in default_config.items():
        if key not in os.environ or os.environ[key] == "":
            os.environ[key] = value
            set_count += 1

    print(f"✅ 环境变量加载完成: {set_count} 个使用默认值, {len(default_config) - set_count} 个使用 Dockerfile ENV 配置")

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
# 2.5 🗄️ 数据库初始化（在导入 app.main 之前执行）
# =================================================================
def init_database():
    """初始化数据库和表"""
    try:
        import psycopg2
        from urllib.parse import urlparse

        # 解析 DATABASE_URL
        db_url = os.getenv("DATABASE_URL", "")
        if not db_url:
            print("⚠️  警告: DATABASE_URL 未设置，跳过数据库初始化")
            return False

        parsed = urlparse(db_url)
        postgres_server = os.getenv("POSTGRES_SERVER", parsed.hostname)
        postgres_port = os.getenv("POSTGRES_PORT", parsed.port or 5432)
        postgres_user = os.getenv("POSTGRES_USER", parsed.username)
        postgres_password = os.getenv("POSTGRES_PASSWORD", parsed.password)
        target_database = os.getenv("POSTGRES_DB", parsed.path.lstrip('/'))

        print("=" * 60)
        print("🗄️  开始数据库初始化...")
        print(f"   服务器: {postgres_server}:{postgres_port}")
        print(f"   数据库: {target_database}")
        print("=" * 60)

        # 1. 先连接到默认的 postgres 数据库
        print("🔌 连接到默认数据库 'postgres'...")
        conn = psycopg2.connect(
            host=postgres_server,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            database="postgres"
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # 2. 检查目标数据库是否存在
        print(f"🔍 检查数据库 '{target_database}' 是否存在...")
        cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target_database,))
        exists = cur.fetchone()

        if not exists:
            print(f"📦 创建数据库 '{target_database}'...")
            cur.execute(f'CREATE DATABASE "{target_database}"')
            print(f"✅ 数据库 '{target_database}' 创建成功")
        else:
            print(f"✅ 数据库 '{target_database}' 已存在")

        cur.close()
        conn.close()

        # 3. 现在导入 SQLAlchemy 并创建表
        from app.database import Base, engine
        from sqlalchemy import text

        print("📊 创建数据库表...")

        # 先启用 pgvector 扩展（如果存在）
        try:
            with engine.connect() as conn:
                # 尝试创建 vector 扩展
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
                conn.commit()
                print("✅ pgvector 扩展已启用")
        except Exception as e:
            print(f"⚠️  警告: 无法启用 pgvector 扩展: {e}")
            print("   如果代码中使用了 Vector 类型，表创建可能会失败")

        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ 数据库表创建成功")

        # 4. 验证关键表是否创建成功
        conn = psycopg2.connect(
            host=postgres_server,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            database=target_database
        )
        cur = conn.cursor()

        tables_to_check = ['users', 'tasks', 'task_view_records']
        all_exist = True
        for table in tables_to_check:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = %s
                );
            """, (table,))
            exists = cur.fetchone()[0]
            status = "✅" if exists else "❌"
            print(f"   {status} 表 '{table}': {'存在' if exists else '不存在'}")
            if not exists:
                all_exist = False

        cur.close()
        conn.close()

        if all_exist:
            print("=" * 60)
            print("✅ 数据库初始化完成!")
            print("=" * 60)
        else:
            print("⚠️  警告: 部分表未创建成功")

        return all_exist

    except Exception as e:
        print(f"❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

# 执行数据库初始化
print("\n🚀 正在启动应用...")
init_success = init_database()
if not init_success:
    print("⚠️  警告: 数据库初始化失败，但应用将继续启动")

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
# 尝试多个路径查找前端构建文件
frontend_paths = [
    os.path.join(current_dir, "backend", "static", "frontend"),  # Docker 构建后的路径
    os.path.join(current_dir, "frontend", "dist"),  # 本地开发路径
]

frontend_dist_path = None
for path in frontend_paths:
    if os.path.exists(path):
        frontend_dist_path = path
        print(f"✅ 找到前端构建目录: {frontend_dist_path}")
        break

if not frontend_dist_path:
    print("⚠️  警告: 未找到前端构建目录，将只提供 API 服务")
    print(f"   查找路径: {frontend_paths}")
else:
    # 挂载前端静态资源
    assets_dir = os.path.join(frontend_dist_path, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")
        print(f"✅ 已挂载前端资源目录: /assets -> {assets_dir}")

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
# 6. 🚀 启动（Celery Worker 与 Uvicorn 并行运行）
# =================================================================
if __name__ == "__main__":
    import subprocess
    import os
    import threading
    import signal
    import sys
    from pathlib import Path
    import socket

    # 🔧 智能选择 Redis 配置：K8s 环境用 K8s Redis，本地开发用本地 Redis
    k8s_redis_url = "redis://:123myredissecret@redis7.gms.svc.cluster.local:6379/1"
    local_redis_url = "redis://localhost:6379/0"

    # 检测是否能连接到 K8s Redis
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('redis7.gms.svc.cluster.local', 6379))
        sock.close()
        use_k8s_redis = (result == 0)
    except Exception:
        use_k8s_redis = False

    # 根据环境选择 Redis URL
    redis_url = k8s_redis_url if use_k8s_redis else local_redis_url

    # 设置环境变量
    os.environ["CELERY_BROKER_URL"] = redis_url
    os.environ["CELERY_RESULT_BACKEND"] = redis_url
    os.environ["REDIS_URL"] = redis_url
    os.environ["CELERY_ENABLED"] = "true"

    print("=" * 60)
    print("🚀 启动模式: Uvicorn + Celery Worker (并行)")
    print(f"   环境: {'K8s 集群' if use_k8s_redis else '本地开发'}")
    print(f"   Celery Broker: {redis_url}")
    print("=" * 60)

    # 用于追踪子进程
    celery_worker_process = None

    def run_celery_worker():
        """在单独的线程中运行 Celery Worker"""
        global celery_worker_process

        # 使用 Python -m celery 方式启动，确保命令能找到
        celery_cmd = [
            sys.executable, "-m", "celery", "-A", "app.tasks.celery_app",
            "worker",
            "--loglevel=info",
            "--concurrency=2",
            "--queues=high_priority,medium_priority,low_priority,default",
            "--max-tasks-per-child=100",
        ]

        print("[Celery Worker] 启动命令:", " ".join(celery_cmd))
        print("[Celery Worker] 工作目录:", os.getcwd())

        try:
            # 🔑 关键修复：设置 PYTHONPATH 确保子进程能找到 app 模块
            worker_env = os.environ.copy()
            backend_path = os.path.join(current_dir, "backend")
            worker_env["PYTHONPATH"] = backend_path + ":" + worker_env.get("PYTHONPATH", "")

            # 使用 Popen 运行，不等待完成
            celery_worker_process = subprocess.Popen(
                celery_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                env=worker_env  # 传递环境变量（包含 PYTHONPATH）
            )

            print(f"[Celery Worker] PID: {celery_worker_process.pid}")

            # 实时输出日志
            for line in celery_worker_process.stdout:
                print(f"[Celery Worker] {line}", end='')

            # Worker 进程退出
            return_code = celery_worker_process.wait()
            print(f"[Celery Worker] 进程退出，返回码: {return_code}")

        except FileNotFoundError as e:
            print(f"[Celery Worker] 启动失败 - 命令未找到: {e}")
            print(f"[Celery Worker] 请确保 celery 包已安装: pip install celery redis")
            import traceback
            traceback.print_exc()
        except Exception as e:
            print(f"[Celery Worker] 启动失败: {e}")
            import traceback
            traceback.print_exc()

    def signal_handler(signum, frame):
        """处理终止信号，清理子进程"""
        print(f"\n[主进程] 收到信号 {signum}，正在关闭...")
        if celery_worker_process:
            print(f"[主进程] 终止 Celery Worker (PID: {celery_worker_process.pid})...")
            celery_worker_process.terminate()
            try:
                celery_worker_process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                celery_worker_process.kill()
        sys.exit(0)

    # 注册信号处理器
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # 🔑 关键修复：使用非 daemon 线程，确保 Worker 不会被回收
    # daemon=False 线程会阻止程序退出，这正是我们需要的
    celery_thread = threading.Thread(target=run_celery_worker, daemon=False)
    celery_thread.start()

    # 等待一下，确保 Worker 启动成功
    import time
    time.sleep(5)  # 增加等待时间到 5 秒

    # 检查 Worker 是否还在运行
    if celery_worker_process and celery_worker_process.poll() is None:
        print("✅ Celery Worker 启动成功")
    else:
        print("⚠️  警告: Celery Worker 可能启动失败，但 Uvicorn 将继续运行")
        if celery_worker_process:
            poll_result = celery_worker_process.poll()
            print(f"⚠️  Worker 进程状态: {poll_result}")

    # 启动 Uvicorn（主线程，阻塞运行）
    print("🚀 正在启动 Uvicorn...")
    uvicorn.run(app, host="0.0.0.0", port=8000)