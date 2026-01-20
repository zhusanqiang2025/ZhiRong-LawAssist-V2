# backend/app/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from .core.config import settings
import os

# 从环境变量读取连接池配置
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "20"))  # 连接池大小
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "30"))  # 最大溢出连接数
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))  # 获取连接超时时间(秒)
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))  # 连接回收时间(秒)

# 检测数据库类型
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

# 创建数据库引擎
if is_sqlite:
    # SQLite 配置（不需要连接池）
    engine = create_engine(
        settings.DATABASE_URL,
        connect_args={"check_same_thread": False},  # SQLite 特定配置
        echo=False,
    )
else:
    # PostgreSQL 配置
    engine = create_engine(
        settings.DATABASE_URL,
        pool_size=DB_POOL_SIZE,  # 连接池大小，默认20
        max_overflow=DB_MAX_OVERFLOW,  # 最大溢出连接数，默认30
        pool_timeout=DB_POOL_TIMEOUT,  # 获取连接超时时间，默认30秒
        pool_recycle=DB_POOL_RECYCLE,  # 连接回收时间，默认1小时
        pool_pre_ping=True,  # 连接前ping检查，防止连接断开
        echo=False,  # 建议生产关闭 echo=True，开发时可打开调试
        connect_args={
            'sslmode': 'disable',
            'connect_timeout': 10,
            'options': '-c statement_timeout=30000'  # 设置SQL语句超时30秒
        },
        # 优化查询性能
        execution_options={
            "isolation_level": "READ COMMITTED"
        }
    )

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 模型基类
Base = declarative_base()

# FastAPI 依赖：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()