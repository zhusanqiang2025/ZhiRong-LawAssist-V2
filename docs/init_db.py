#!/usr/bin/env python3
"""
数据库初始化脚本
用于创建 legal_assistant_db 数据库和所有必要的表
"""
import os
import sys

# 添加 backend 目录到 Python 路径
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "backend")
sys.path.insert(0, backend_path)

def init_database():
    """初始化数据库"""
    print("=" * 60)
    print("开始初始化数据库...")
    print("=" * 60)

    try:
        # 1. 连接到 PostgreSQL 默认数据库
        import psycopg2
        from urllib.parse import urlparse

        # 从环境变量读取数据库配置
        DATABASE_URL = os.getenv("DATABASE_URL",
            "postgresql://postgres:postgres@postgres18-0.postgres18.gms.svc.cluster.local:5432/legal_assistant_db")

        parsed = urlparse(DATABASE_URL)

        postgres_server = parsed.hostname or os.getenv("POSTGRES_SERVER", "localhost")
        postgres_port = parsed.port or os.getenv("POSTGRES_PORT", 5432)
        postgres_user = parsed.username or os.getenv("POSTGRES_USER", "postgres")
        postgres_password = parsed.password or os.getenv("POSTGRES_PASSWORD", "postgres")
        target_database = parsed.path.lstrip('/') if parsed.path else os.getenv("POSTGRES_DB", "legal_assistant_db")

        print(f"\n📋 数据库配置:")
        print(f"   服务器: {postgres_server}:{postgres_port}")
        print(f"   用户: {postgres_user}")
        print(f"   目标数据库: {target_database}")

        # 2. 先连接到默认的 postgres 数据库
        print(f"\n🔌 连接到默认数据库 'postgres'...")
        conn = psycopg2.connect(
            host=postgres_server,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            database="postgres"
        )
        conn.set_isolation_level(psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        # 3. 检查目标数据库是否存在
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

        # 4. 导入 SQLAlchemy 并创建表
        print(f"\n🔗 连接到数据库 '{target_database}'...")
        from app.database import engine, Base
        from app.models.user import User
        from app.models.task import Task
        from app.models.task_view import TaskViewRecord

        print("📊 创建数据库表...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        print("✅ 数据库表创建成功")

        # 5. 验证表是否创建成功
        print("\n🔍 验证表是否存在...")
        conn = psycopg2.connect(
            host=postgres_server,
            port=postgres_port,
            user=postgres_user,
            password=postgres_password,
            database=target_database
        )
        cur = conn.cursor()

        tables_to_check = ['users', 'tasks', 'task_view_records']
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

        cur.close()
        conn.close()

        print("\n" + "=" * 60)
        print("✅ 数据库初始化完成!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"\n❌ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)
