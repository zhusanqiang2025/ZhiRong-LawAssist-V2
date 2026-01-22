#!/usr/bin/env python3
"""
本地测试脚本 - 通过 dbgate 服务测试连接
请确保已安装 psycopg2-binary 和 redis
"""
import os

# 安装依赖
os.system("pip install psycopg2-binary redis -q")

import psycopg2
import redis

print("="*60)
print("🧪 本地数据库连接测试")
print("="*60)

# PostgreSQL 连接配置
pg_config = {
    "host": "postgres18-0-postgres18.gmv.cluster.local",
    "port": 5432,
    "user": "postgres",
    "password": "postgres",
}

# Redis 连接配置
redis_config = {
    "host": "redis7.gmv.cluster.local",
    "port": 6379,
    "decode_responses": True,
}

# 测试 PostgreSQL
print("\n📊 测试 PostgreSQL...")
try:
    # 连接到默认 postgres 数据库
    conn = psycopg2.connect(**pg_config, database="postgres")
    cur = conn.cursor()

    # 检查 legal_assistant_db 是否存在
    cur.execute("SELECT 1 FROM pg_database WHERE datname='legal_assistant_db'")
    exists = cur.fetchone()

    if exists:
        print("✅ 数据库 'legal_assistant_db' 已存在")
    else:
        print("⚠️  数据库 'legal_assistant_db' 不存在")
        print("   需要创建！请在 dbgate 中执行:")
        print("   CREATE DATABASE legal_assistant_db;")

    # 列出所有数据库
    cur.execute("SELECT datname FROM pg_database WHERE datistemplate=false")
    print("\n现有数据库:")
    for db in cur.fetchall():
        print(f"   - {db[0]}")

    cur.close()
    conn.close()

except Exception as e:
    print(f"❌ PostgreSQL 连接失败: {e}")

# 测试 Redis
print("\n🔴 测试 Redis...")
try:
    r = redis.Redis(**redis_config, socket_connect_timeout=5)
    r.ping()
    print("✅ Redis 连接成功（无需密码）")

    # 获取信息
    info = r.info()
    print(f"   版本: {info.get('redis_version')}")
    print(f"   连接数: {info.get('connected_clients')}")

except redis.AuthenticationError:
    print("❌ Redis 需要密码认证")
    print("   请提供 Redis 密码")
except Exception as e:
    print(f"❌ Redis 连接失败: {e}")

print("\n" + "="*60)
