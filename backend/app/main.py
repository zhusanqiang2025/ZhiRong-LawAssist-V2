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
    """初始化默认用户 - 仅在开发环境创建"""
    # 只在开发环境创建默认用户
    if os.getenv("ENVIRONMENT") == "production":
        logger.info("Production environment detected. Skipping default user creation.")
        return

    from sqlalchemy.orm import Session
    from app.database import SessionLocal

    db: Session = SessionLocal()
    try:
        # 检查是否已存在用户
        user_count = db.query(User).count()
        if user_count == 0:
            # 从环境变量读取默认管理员账户信息
            # ⚠️  安全警告: 生产环境必须使用环境变量设置强密码
            default_email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD")

            # 如果未设置环境变量，生成随机密码并记录
            if not default_password:
                import secrets
                default_password = secrets.token_urlsafe(16)
                logger.error("=" * 80)
                logger.error("SECURITY WARNING: DEFAULT_ADMIN_PASSWORD not set in environment!")
                logger.error(f"A random password has been generated: {default_password}")
                logger.error("Please save this password and login immediately to change it!")
                logger.error("=" * 80)

            # 验证密码强度
            if len(default_password) < 8:
                logger.error("Default admin password is too weak (min 8 characters required)")
                logger.error("Generating a secure random password instead")
                import secrets
                default_password = secrets.token_urlsafe(16)

            # 创建默认用户（管理员权限）
            default_user = User(
                email=default_email,
                hashed_password=get_password_hash(default_password),
                is_admin=True,  # 设置为管理员
                is_active=True,
                is_superuser=True
            )
            db.add(default_user)
            db.commit()
            db.refresh(default_user)
            logger.info(f"Default admin user created: {default_email} (is_admin=True)")
            logger.warning("SECURITY WARNING: Please change the default password after first login!")
        else:
            logger.info(f"Users already exist in database ({user_count} users). Skipping default user creation.")
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

# 从环境变量读取生产环境域名
production_origins = os.getenv("ALLOWED_ORIGINS", "").split(",")
if production_origins and production_origins[0]:
    allowed_origins.extend([origin.strip() for origin in production_origins if origin.strip()])

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

    logger.info(f"[OnlyOffice Proxy] {request.method} {full_path} -> {target_url}")

    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # 转发请求
            if request.method == "GET":
                response = client.get(
                    target_url,
                    params=query_params,
                    headers={"Accept": "application/javascript, text/html, */*"}
                )
            else:
                # 其他方法（POST 等）
                content = await request.body()
                response = client.request(
                    request.method,
                    target_url,
                    params=query_params,
                    content=content,
                    headers=dict(request.headers)
                )

            # 返回响应
            return Response(
                content=response.content,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.headers.get("content-type", "application/octet-stream")
            )

        except httpx.RequestError as e:
            logger.error(f"[OnlyOffice Proxy] 连接失败: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"OnlyOffice 服务不可用: {str(e)}。请联系管理员检查 OnlyOffice 服务状态。"
            )
        except Exception as e:
            logger.error(f"[OnlyOffice Proxy] 代理失败: {e}")
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
        "architecture": "Standardized v1 Router"
    }

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
