# backend/app/main.py (重构版 v4.0 - 路由架构标准化)
"""
法律文书生成助手应用入口
路由架构标准化：所有业务 API 统一收归到 /api/v1 命名空间
"""
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

import logging
import sys
import time
import os
import asyncio
import json
from typing import Dict
import httpx

from app.database import Base, engine
from app.models.user import User
from app.models.task import Task
from app.models.task_view import TaskViewRecord

# ==================== 核心路由导入（唯一）====================
from app.api.v1.router import api_router  # 统一 v1 路由入口
from app.api.websocket import manager  # WebSocket 连接管理器
from app.core.security import get_password_hash
from app.core.exceptions import setup_exception_handlers

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ==================== 数据库初始化 ====================
# 首先尝试连接到 PostgreSQL 默认数据库，检查目标数据库是否存在
# 如果不存在，则创建目标数据库
logger.info("Checking if database exists...")
try:
    import psycopg2
    from urllib.parse import urlparse

    # 解析 DATABASE_URL 获取连接信息
    db_url = os.getenv("DATABASE_URL", "")
    parsed = urlparse(db_url)

    postgres_server = os.getenv("POSTGRES_SERVER", parsed.hostname)
    postgres_port = os.getenv("POSTGRES_PORT", parsed.port or 5432)
    postgres_user = os.getenv("POSTGRES_USER", parsed.username)
    postgres_password = os.getenv("POSTGRES_PASSWORD", parsed.password)
    target_database = os.getenv("POSTGRES_DB", parsed.path.lstrip('/'))

    # 先连接到默认的 postgres 数据库
    conn = psycopg2.connect(
        host=postgres_server,
        port=postgres_port,
        user=postgres_user,
        password=postgres_password,
        database="postgres"  # 默认数据库
    )
    conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    # 检查目标数据库是否存在
    cur.execute("SELECT 1 FROM pg_database WHERE datname=%s", (target_database,))
    exists = cur.fetchone()

    if not exists:
        logger.info(f"Database '{target_database}' does not exist. Creating...")
        cur.execute(f'CREATE DATABASE "{target_database}"')
        logger.info(f"Database '{target_database}' created successfully.")
    else:
        logger.info(f"Database '{target_database}' already exists.")

    cur.close()
    conn.close()

except Exception as e:
    logger.warning(f"Could not check/create database: {e}")
    logger.warning("Assuming database exists or will be created manually...")

# 现在创建表
logger.info("Creating database tables if they don't exist...")
try:
    Base.metadata.create_all(bind=engine, checkfirst=True)
    logger.info("Database tables checked/created.")
except Exception as e:
    logger.error(f"Failed to create database tables: {e}")


def init_default_user():
    """
    初始化默认管理员用户

    支持两种场景：
    1. 数据库为空时创建管理员
    2. 管理员用户已存在但不是管理员时，提升为管理员
    """
    db: Session = SessionLocal()
    try:
        # 从环境变量读取默认管理员账户信息
        default_email = os.getenv("DEFAULT_ADMIN_EMAIL")
        default_password = os.getenv("DEFAULT_ADMIN_PASSWORD")

        # 如果未配置环境变量，跳过（依赖 seed_production_data.py）
        if not default_email or not default_password:
            logger.info("DEFAULT_ADMIN_EMAIL or DEFAULT_ADMIN_PASSWORD not set, skipping")
            return

        # 验证密码强度
        if len(default_password) < 8:
            logger.error("DEFAULT_ADMIN_PASSWORD is too weak (min 8 characters required), skipping")
            return

        # 检查用户是否已存在
        existing_user = db.query(User).filter(User.email == default_email).first()

        if existing_user:
            # 用户已存在，检查是否是管理员
            if existing_user.is_admin and existing_user.is_superuser:
                logger.info(f"Admin user already exists: {default_email}")
            else:
                # 提升为管理员
                existing_user.is_admin = True
                existing_user.is_superuser = True
                db.commit()
                logger.info(f"✓ Promoted existing user to admin: {default_email}")
        else:
            # 创建新的管理员用户
            default_user = User(
                email=default_email,
                hashed_password=get_password_hash(default_password),
                is_admin=True,
                is_active=True,
                is_superuser=True
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
            logger.info(f"✓ Admin user created: {default_email} (is_admin=True)")
            logger.warning("SECURITY WARNING: Please change the default password after first login!")

    except Exception as e:
        logger.error(f"Error initializing default user: {e}")
        db.rollback()
    finally:
        db.close()


logger.info("Initializing default user if needed...")
try:
    init_default_user()
except Exception as e:
    logger.error(f"Failed to initialize default user: {e}")

# ==================== 生产环境数据初始化 ====================
# 启动时检查并导入必要的数据（管理员、规则、知识图谱）
# 设计原则：
# 1. 幂等性：可以安全地重复执行
# 2. 降级处理：环境变量未配置时跳过，不中断应用启动
# 3. 复用现有：调用所有现有的初始化函数
logger.info("Checking if production data seeding is needed...")
try:
    from scripts.seed_production_data import seed_production_data
    seed_production_data()
except Exception as e:
    logger.error(f"Production data seeding encountered an error (application will continue): {e}")
    # 不中断应用启动

# ==================== FastAPI 应用创建 ====================
app = FastAPI(
    title="法律文书生成助手 API",
    description="专业的法律文书生成和分析平台 - 路由架构标准化版本",
    version="4.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# ==================== Redis Pub/Sub 监听器（已移除，使用内存缓存）====================
# 任务进度现在使用内存缓存或 WebSocket 直接推送，不再需要 Redis

# ==================== 静态文件挂载 ====================
# 确保 storage/uploads 目录存在
os.makedirs("storage/uploads", exist_ok=True)
# 挂载目录：访问 http://IP:8000/storage/xxx -> 映射到本地 storage/xxx
app.mount("/storage", StaticFiles(directory="storage"), name="storage")

# ==================== 前端静态文件配置（生产环境） ====================
# 尝试多种方式定位前端静态文件目录
# 方式1: 相对于 main.py 的路径
frontend_static_dir_relative = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "static", "frontend"))
# 方式2: 直接使用绝对路径
frontend_static_dir_absolute = "/app/static/frontend"

# 选择存在的路径
if os.path.exists(frontend_static_dir_absolute):
    frontend_static_dir = frontend_static_dir_absolute
    logger.info(f"[Frontend] Using absolute path: {frontend_static_dir}")
elif os.path.exists(frontend_static_dir_relative):
    frontend_static_dir = frontend_static_dir_relative
    logger.info(f"[Frontend] Using relative path: {frontend_static_dir}")
else:
    frontend_static_dir = frontend_static_dir_absolute  # 使用绝对路径作为默认值
    logger.warning(f"[Frontend] Frontend directory not found at:")
    logger.warning(f"[Frontend]   - Absolute: {frontend_static_dir_absolute}")
    logger.warning(f"[Frontend]   - Relative: {frontend_static_dir_relative}")
    logger.warning(f"[Frontend] Will try to continue anyway...")

# 挂载前端静态资源
if os.path.exists(frontend_static_dir):
    # 挂载 assets 目录（JS、CSS 等静态资源）
    assets_dir = os.path.join(frontend_static_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    # 挂载其他静态资源（如 public 目录中的文件）
    public_dir = os.path.join(frontend_static_dir, "public")
    if os.path.exists(public_dir):
        app.mount("/public", StaticFiles(directory=public_dir), name="frontend-public")

# SPA 前端根路径标记 - 将在文件末尾处理
_frontend_spa_enabled = os.path.exists(frontend_static_dir)

# 调试日志
logger.info(f"[Frontend] Static directory check:")
logger.info(f"[Frontend]   - frontend_static_dir = {frontend_static_dir}")
logger.info(f"[Frontend]   - exists = {os.path.exists(frontend_static_dir)}")
logger.info(f"[Frontend]   - _frontend_spa_enabled = {_frontend_spa_enabled}")
if os.path.exists(frontend_static_dir):
    try:
        files = os.listdir(frontend_static_dir)
        logger.info(f"[Frontend]   - Files in directory: {files[:5]}...")  # 只显示前5个文件
        index_path = os.path.join(frontend_static_dir, "index.html")
        logger.info(f"[Frontend]   - index.html exists: {os.path.exists(index_path)}")
    except Exception as e:
        logger.error(f"[Frontend]   - Error listing directory: {e}")

# ==================== 安全中间件配置 ====================
# 安全的 CORS 配置
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite 默认端口
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://localhost:8081",  # 前端端口
    "http://localhost:8089",  # 前端端口（当前实际运行端口）
    "http://localhost:8082",  # OnlyOffice Document Server
    "http://127.0.0.1:8082",  # OnlyOffice Document Server (本地回环)
    "https://legal-assistant-v3.azgpu02.azshentong.com",  # 生产环境域名
    "http://180.184.47.218:3001",  # 生产服务器前端
    "http://180.184.47.218:5173",  # 生产服务器前端（开发端口）
    "http://180.184.47.218:8081",  # 生产服务器前端（备用端口）
    "http://180.184.47.218:8089",  # 生产服务器前端（备用端口）
    "http://180.184.47.218:8083",  # 生产服务器 OnlyOffice
]

# 从环境变量读取生产环境域名（支持逗号分隔的多个域名）
production_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if production_origins and production_origins[0]:
    allowed_origins.extend([origin.strip() for origin in production_origins if origin.strip()])

# ⭐ 自动将 FRONTEND_PUBLIC_URL 添加到允许列表（用于飞书通知跳转）
frontend_public_url = os.getenv("FRONTEND_PUBLIC_URL", "")
if frontend_public_url and frontend_public_url not in allowed_origins:
    allowed_origins.append(frontend_public_url)
    logger.info(f"[CORS] 自动添加 FRONTEND_PUBLIC_URL 到允许列表: {frontend_public_url}")

# 安全中间件配置
if os.getenv("ENVIRONMENT") == "production":
    # 生产环境安全配置
    app.add_middleware(HTTPSRedirectMiddleware)  # 强制 HTTPS
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["*"],
)

# 请求大小限制中间件
@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    content_length = request.headers.get("content-length")
    # 只对POST请求进行大小限制检查
    if content_length and request.method == "POST":
        max_size = int(os.getenv("MAX_REQUEST_SIZE", 50 * 1024 * 1024))  # 增加到50MB
        if int(content_length) > max_size:
            raise HTTPException(
                status_code=413,
                detail=f"Request entity too large. Max size: {max_size // (1024*1024)}MB"
            )

    response = await call_next(request)
    return response

# ==================== 应用启动事件 ====================
@app.on_event("startup")
async def startup_event():
    """
    应用启动时执行的初始化操作

    包括：
    1. 启动飞书长连接（如果配置了飞书集成）
    """
    logger.info("=" * 60)
    logger.info("🚀 应用启动中...")
    logger.info("=" * 60)

    # 启动飞书长连接（仅在生产环境或明确启用时）
    feishu_enabled = os.getenv("FEISHU_ENABLED", "false").lower() == "true"
    if feishu_enabled:
        try:
            # 导入并启动飞书长连接
            from app.api.v1.endpoints.feishu_callback import start_feishu_long_connection
            start_feishu_long_connection()
            logger.info("✅ 飞书长连接已启动")
        except Exception as e:
            logger.warning(f"⚠️ 飞书长连接启动失败: {e}")
            logger.warning("飞书集成功能将不可用，但不影响其他功能")
    else:
        logger.info("ℹ️ 飞书集成未启用（FEISHU_ENABLED=false）")

    logger.info("=" * 60)
    logger.info("✅ 应用启动完成")
    logger.info("=" * 60)

# 安全头中间件
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # 添加安全头
    response.headers["X-Content-Type-Options"] = "nosniff"

    # X-Frame-Options: 允许 OnlyOffice 和同源嵌入
    # OnlyOffice Document Server 需要在 iframe 中加载文档
    request_path = request.url.path
    if request_path.startswith("/storage/"):
        # 文件资源允许被 OnlyOffice 嵌入
        # 不设置 X-Frame-Options，使用 Content-Security-Policy 代替
        response.headers["Content-Security-Policy"] = "frame-ancestors *"
    else:
        response.headers["X-Frame-Options"] = "DENY"

    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    if os.getenv("ENVIRONMENT") == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    return response

# ==================== 统一路由注册（核心规范） ====================
# 规范：所有业务 API 必须通过 api_router 统一挂载到 /api/v1
# 禁止：在 main.py 中直接 include_router 具体业务模块

# 统一 v1 路由挂载
app.include_router(api_router, prefix="/api/v1")

# 设置统一的异常处理器
setup_exception_handlers(app)

# ==================== 根路径与健康检查 ====================

# ==================== OnlyOffice 代理 ====================
# 在 K8s 环境中，OnlyOffice 静态资源通过后端代理
ONLYOFFICE_URL = os.getenv(
    "ONLYOFFICE_URL",
    "http://legal_assistant_v3_onlyoffice:80"  # K8s 内部地址
)


@app.get("/onlyoffice/{full_path:path}")
async def proxy_onlyoffice(full_path: str, request: Request):
    """
    OnlyOffice 静态资源代理

    当 K8s 中 OnlyOffice 服务运行时，后端转发请求
    解决 MIME type 和 CORS 问题
    """
    # 构建目标 URL
    target_url = f"{ONLYOFFICE_URL}/{full_path}"
    if request.url.query:
        target_url += f"?{request.url.query}"

    # 转发查询参数
    query_params = dict(request.query_params)

    # 🔍 根据文件扩展名确定 MIME type（在请求前就确定，避免 500 错误）
    content_type = "application/octet-stream"  # 默认
    path_without_query = full_path.split("?")[0]  # 移除查询参数
    if path_without_query.endswith(".js"):
        content_type = "application/javascript; charset=utf-8"
    elif path_without_query.endswith(".css"):
        content_type = "text/css; charset=utf-8"
    elif path_without_query.endswith(".html"):
        content_type = "text/html; charset=utf-8"
    elif path_without_query.endswith(".json"):
        content_type = "application/json; charset=utf-8"

    logger.info(f"[OnlyOffice Proxy] {request.method} {full_path} -> {target_url}")
    logger.info(f"[OnlyOffice Proxy] 预设 MIME type: {content_type}")

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            # 转发请求
            if request.method == "GET":
                response = await client.get(
                    target_url,
                    params=query_params,
                    headers={"Accept": "application/javascript, text/html, */*"}
                )
            else:
                # 其他方法（POST 等）
                content = await request.body()
                response = await client.request(
                    request.method,
                    target_url,
                    params=query_params,
                    content=content,
                    headers=dict(request.headers)
                )

            logger.info(f"[OnlyOffice Proxy] 响应: status={response.status_code}, original-content-type={response.headers.get('content-type', 'N/A')}")

            # 返回响应（强制使用预设的 MIME type）
            return Response(
                content=response.content,
                status_code=response.status_code,
                media_type=content_type
            )

    except httpx.RequestError as e:
        logger.error(f"[OnlyOffice Proxy] 连接失败: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"OnlyOffice 服务不可用: {str(e)}。请联系管理员检查 OnlyOffice 服务状态。"
        )
    except Exception as e:
        logger.error(f"[OnlyOffice Proxy] 代理失败: {e}")
        import traceback
        logger.error(f"[OnlyOffice Proxy] 错误堆栈: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"代理请求失败: {str(e)}")


@app.get("/")
def read_root(request: Request):
    """
    API 根端点
    开发环境：返回 API 信息
    生产环境（前端已构建）：返回前端 index.html
    """
    # 生产环境：如果前端已构建，返回 index.html
    if _frontend_spa_enabled:
        index_file = os.path.join(frontend_static_dir, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)

    # 开发环境：返回 API 信息
    return {
        "success": True,
        "message": "欢迎使用法律文书助手 API v4.0 (路由架构标准化版)",
        "version": "4.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api_base": "/api/v1",
        "frontend": "Frontend not built. In development, use 'npm run dev' in frontend directory."
    }


@app.get("/health")
def health_check(request: Request):
    """
    健康检查端点
    """
    return {
        "success": True,
        "status": "healthy",
        "timestamp": time.time(),
        "version": "4.0.0",
        "architecture": "Standardized v1 Router",
        "services": {
            "onlyoffice_url": ONLYOFFICE_URL,
            "celery_enabled": os.getenv("CELERY_ENABLED", "false")
        }
    }


@app.get("/health/onlyoffice")
async def check_onlyoffice_health():
    """
    OnlyOffice 服务健康检查
    用于调试 OnlyOffice 连接问题
    """
    import httpx
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 尝试连接 OnlyOffice
            response = await client.get(
                f"{ONLYOFFICE_URL}/",
                headers={"User-Agent": "HealthCheck/1.0"}
            )
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "service_url": ONLYOFFICE_URL,
                "message": "OnlyOffice 服务可访问" if response.status_code == 200 else f"OnlyOffice 返回状态码: {response.status_code}"
            }
    except Exception as e:
        return {
            "success": False,
            "service_url": ONLYOFFICE_URL,
            "error": str(e),
            "message": "无法连接到 OnlyOffice 服务"
        }


@app.get("/health/celery")
async def check_celery_health():
    """
    Celery Worker 健康检查

    检查 Celery Worker 是否正在运行
    """
    try:
        from app.tasks.celery_app import celery_app

        # 使用 Celery 的 inspect API 检查活跃的 workers
        inspector = celery_app.control.inspect(timeout=5.0)

        # 获取活跃的 workers
        active_workers = inspector.active()

        if active_workers:
            # Worker 正在运行
            worker_count = len(active_workers)
            worker_stats = {}
            for worker_name, tasks in active_workers.items():
                worker_stats[worker_name] = {
                    "active_tasks": len(tasks) if tasks else 0,
                    "tasks": [t.get("id", "unknown") for t in tasks[:5]] if tasks else []
                }

            return {
                "success": True,
                "status": "healthy",
                "worker_count": worker_count,
                "workers": list(active_workers.keys()),
                "worker_stats": worker_stats,
                "message": f"Celery Worker 运行中 ({worker_count} 个 worker)"
            }
        else:
            # 没有活跃的 workers
            return {
                "success": False,
                "status": "unhealthy",
                "workers": [],
                "message": "未检测到活跃的 Celery Worker",
                "troubleshooting": "检查后端日志，确认 Celery Worker 是否成功启动"
            }

    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "message": f"Celery 健康检查失败: {str(e)}"
        }


@app.get("/health/celery/test")
async def test_celery_task():
    """
    测试 Celery 任务执行

    提交一个简单的测试任务，验证整个流程是否正常
    """
    try:
        from app.tasks.celery_app import health_check

        # 提交测试任务
        result = health_check.apply_async(expires=30)

        # 等待结果（最多等待 10 秒）
        try:
            task_result = result.get(timeout=10)
            return {
                "success": True,
                "status": "passed",
                "task_id": result.id,
                "result": task_result,
                "message": "Celery 任务执行成功"
            }
        except Exception as e:
            return {
                "success": False,
                "status": "failed",
                "task_id": result.id,
                "error": str(e),
                "message": "Celery 任务执行失败或超时"
            }

    except Exception as e:
        return {
            "success": False,
            "status": "error",
            "error": str(e),
            "message": f"无法提交测试任务: {str(e)}"
        }


@app.get("/health/diagnostics")
async def system_diagnostics():
    """
    系统综合诊断

    检查所有可能导致异步任务失败的原因：
    - Redis 连接
    - Celery 配置
    - 环境变量
    - Worker 进程状态
    """
    diagnostics = {
        "timestamp": time.time(),
        "checks": {}
    }

    # 1. 检查环境变量
    diagnostics["checks"]["environment"] = {
        "CELERY_BROKER_URL": os.getenv("CELERY_BROKER_URL", "NOT_SET"),
        "CELERY_RESULT_BACKEND": os.getenv("CELERY_RESULT_BACKEND", "NOT_SET"),
        "REDIS_URL": os.getenv("REDIS_URL", "NOT_SET"),
        "CELERY_ENABLED": os.getenv("CELERY_ENABLED", "NOT_SET"),
        "status": "configured" if os.getenv("CELERY_BROKER_URL") else "missing"
    }

    # 2. 检查 Redis 连接
    redis_status = {"status": "unknown", "error": None}
    try:
        import redis
        redis_url = os.getenv("CELERY_BROKER_URL", "")
        if redis_url:
            if redis_url.startswith("redis://"):
                r = redis.from_url(redis_url, socket_timeout=5)
                r.ping()
                redis_status["status"] = "connected"
                redis_status["url"] = redis_url[:50] + "..." if len(redis_url) > 50 else redis_url
            else:
                redis_status["status"] = "invalid_url"
                redis_status["error"] = "Invalid Redis URL format"
        else:
            redis_status["status"] = "not_configured"
            redis_status["error"] = "CELERY_BROKER_URL not set"
    except Exception as e:
        redis_status["status"] = "failed"
        redis_status["error"] = str(e)
    diagnostics["checks"]["redis"] = redis_status

    # 3. 检查 Celery 配置
    celery_status = {"status": "unknown", "error": None}
    try:
        from app.tasks.celery_app import celery_app
        celery_status["broker_url"] = str(celery_app.conf.broker_url)[:80] + "..."
        celery_status["result_backend"] = str(celery_app.conf.result_backend)[:80] + "..."
        celery_status["task_routes"] = list(celery_app.conf.task_routes.keys()) if celery_app.conf.task_routes else []
        celery_status["status"] = "configured"
    except Exception as e:
        celery_status["status"] = "error"
        celery_status["error"] = str(e)
    diagnostics["checks"]["celery_config"] = celery_status

    # 4. 检查 Celery Worker 状态
    worker_status = {"status": "unknown", "error": None}
    try:
        from app.tasks.celery_app import celery_app
        inspector = celery_app.control.inspect(timeout=3.0)
        active = inspector.active()
        registered = inspector.registered()

        if active:
            worker_status["status"] = "running"
            worker_status["workers"] = list(active.keys())
            worker_status["active_tasks"] = {k: len(v) for k, v in active.items()}
        else:
            worker_status["status"] = "no_workers"
            worker_status["message"] = "未检测到活跃的 Celery Worker"

        if registered:
            worker_status["registered_tasks"] = {k: len(v) for k, v in registered.items()}
    except Exception as e:
        worker_status["status"] = "error"
        worker_status["error"] = str(e)
    diagnostics["checks"]["celery_worker"] = worker_status

    # 5. 综合评估
    issues = []
    if diagnostics["checks"]["redis"]["status"] != "connected":
        issues.append(f"Redis 连接失败: {diagnostics['checks']['redis'].get('error', 'Unknown')}")
    if diagnostics["checks"]["celery_worker"]["status"] in ["no_workers", "error"]:
        issues.append(f"Celery Worker 未运行: {diagnostics['checks']['celery_worker'].get('error', 'Unknown')}")
    if not os.getenv("CELERY_BROKER_URL"):
        issues.append("CELERY_BROKER_URL 环境变量未设置")

    diagnostics["summary"] = {
        "overall_status": "healthy" if not issues else "unhealthy",
        "issues": issues,
        "recommendation": "所有检查通过" if not issues else "请检查上述问题"
    }

    return diagnostics


@app.get("/health/debug/celery-command")
async def debug_celery_command():
    """
    调试 Celery 命令是否可用

    测试 celery 命令是否能找到并执行
    """
    import subprocess
    import sys

    result = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "tests": {}
    }

    # 测试 1: celery 命令是否在 PATH 中
    try:
        which_result = subprocess.run(
            ["which", "celery"],
            capture_output=True,
            text=True,
            timeout=5
        )
        result["tests"]["which_celery"] = {
            "found": which_result.returncode == 0,
            "path": which_result.stdout.strip() if which_result.returncode == 0 else None
        }
    except Exception as e:
        result["tests"]["which_celery"] = {"error": str(e)}

    # 测试 2: python -m celery 是否可用
    try:
        test_result = subprocess.run(
            [sys.executable, "-m", "celery", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        result["tests"]["celery_version"] = {
            "success": test_result.returncode == 0,
            "output": test_result.stdout.strip(),
            "error": test_result.stderr.strip()
        }
    except Exception as e:
        result["tests"]["celery_version"] = {"error": str(e)}

    # 测试 3: 检查是否能导入 celery 模块
    try:
        import celery
        result["tests"]["import_celery"] = {
            "success": True,
            "version": celery.__version__
        }
    except ImportError as e:
        result["tests"]["import_celery"] = {
            "success": False,
            "error": str(e)
        }

    # 测试 4: 检查是否能导入 redis 模块
    try:
        import redis
        result["tests"]["import_redis"] = {
            "success": True,
            "version": redis.__version__
        }
    except ImportError as e:
        result["tests"]["import_redis"] = {
            "success": False,
            "error": str(e)
        }

    # 测试 5: 尝试运行 celery inspect（测试基本功能）
    try:
        inspect_result = subprocess.run(
            [sys.executable, "-m", "celery", "inspect", "ping"],
            capture_output=True,
            text=True,
            timeout=5,
            env={**os.environ, "CELERY_BROKER_URL": os.getenv("CELERY_BROKER_URL")}
        )
        result["tests"]["celery_inspect"] = {
            "success": inspect_result.returncode == 0,
            "output": inspect_result.stdout.strip()[:200],
            "error": inspect_result.stderr.strip()[:200]
        }
    except Exception as e:
        result["tests"]["celery_inspect"] = {"error": str(e)}

    return result


# ==================== SPA 前端路由处理（放在最后作为 catch-all） ====================
# 排除的路径前缀（WebSocket 已移至 /api/v1/tasks/ws，无需 /ws 排除）
_EXCLUDED_PREFIXES = ("/api", "/storage", "/health", "/docs", "/redoc", "/assets", "/public", "/openapi.json", "/onlyoffice")


@app.get("/{full_path:path}", include_in_schema=False)
async def catch_all_spa(request: Request, full_path: str = ""):
    """
    SPA 前端路由处理
    所有未匹配的路径返回 index.html（用于前端 React Router）
    """
    # 检查是否是排除的路径（API、静态资源等）
    if request.url.path.startswith(_EXCLUDED_PREFIXES):
        raise HTTPException(status_code=404, detail="Not Found")

    # 检查前端是否已构建
    if not _frontend_spa_enabled:
        raise HTTPException(status_code=404, detail="Frontend not built. Use 'npm run dev' for development.")

    # 返回 index.html
    index_file = os.path.join(frontend_static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend index.html not found")
