#!/usr/bin/env python3
"""
K8s 容器内数据库连接测试脚本
部署后在容器内运行此脚本验证连接
"""
import os
import sys
import socket
import subprocess

print("="*60)
print("🧪 K8s 环境数据库连接测试")
print("="*60)

# 1. 测试 DNS 解析
print("\n1️⃣ 测试 DNS 解析...")
hosts = [
    "redis7.gms.svc.cluster.local",
    "postgres18-0.postgres18.gms.svc.cluster.local",
]

for host in hosts:
    try:
        ip = socket.gethostbyname(host)
        print(f"✅ {host} -> {ip}")
    except socket.gaierror:
        print(f"❌ {host} - DNS 解析失败")

# 2. 测试端口连通性
print("\n2️⃣ 测试端口连通性...")
services = [
    ("redis7.gms.svc.cluster.local", 6379),
    ("postgres18-0.postgres18.gms.svc.cluster.local", 5432),
]

for host, port in services:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((host, port))
        if result == 0:
            print(f"✅ {host}:{port} - 端口开放")
        else:
            print(f"❌ {host}:{port} - 端口不可达 (错误码: {result})")
        sock.close()
    except Exception as e:
        print(f"❌ {host}:{port} - {e}")

# 3. 测试 PostgreSQL 连接
print("\n3️⃣ 测试 PostgreSQL 连接...")
try:
    import psycopg2
    conn = psycopg2.connect(
        host="postgres18-0.postgres18.gms.svc.cluster.local",
        port=5432,
        user="postgres",
        password="postgres",
        database="postgres"  # 先连默认数据库
    )
    print("✅ PostgreSQL 认证成功")

    # 检查目标数据库
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname='legal_assistant_db'")
    exists = cur.fetchone()

    if exists:
        print("✅ 数据库 'legal_assistant_db' 已存在")
    else:
        print("⚠️  数据库 'legal_assistant_db' 不存在，需要创建")
        print("   请在 dbgate 中执行: CREATE DATABASE legal_assistant_db;")

    cur.close()
    conn.close()

except ImportError:
    print("⚠️  psycopg2 未安装，跳过 PostgreSQL 测试")
except psycopg2.OperationalError as e:
    print(f"❌ PostgreSQL 连接失败: {e}")
    if "password authentication failed" in str(e):
        print("   密码错误，请检查 POSTGRES_PASSWORD")
    elif "database" in str(e).lower() and "does not exist" in str(e).lower():
        print("   目标数据库不存在")

# 4. 测试 Redis 连接
print("\n4️⃣ 测试 Redis 连接...")
try:
    import redis
    r = redis.Redis(
        host="redis7.gms.svc.cluster.local",
        port=6379,
        decode_responses=True,
        socket_connect_timeout=5
    )
    r.ping()
    print("✅ Redis 连接成功（无需密码）")

    # 测试读写
    r.set("test_key", "test_value", ex=10)
    value = r.get("test_key")
    if value == "test_value":
        print("✅ Redis 读写测试通过")

except ImportError:
    print("⚠️  redis 未安装，跳过 Redis 测试")
except redis.AuthenticationError:
    print("❌ Redis 需要密码认证")
except redis.ConnectionError as e:
    print(f"❌ Redis 连接失败: {e}")

# 5. 显示环境变量
print("\n5️⃣ 当前环境变量配置...")
print(f"POSTGRES_SERVER: {os.getenv('POSTGRES_SERVER', '未设置')}")
print(f"REDIS_HOST: {os.getenv('REDIS_HOST', '未设置')}")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', '未设置')[:50]}...")

print("\n" + "="*60)
print("测试完成")
print("="*60)
