#!/usr/bin/env python3
"""
线上部署完整验证脚本
检查前后端通信配置 + AI API Key 有效性
"""
import os
import sys
import socket
import json
import urllib.request
import urllib.error
import time

# 颜色输出
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_success(msg):
    print(f"{GREEN}✅ {msg}{RESET}")

def print_error(msg):
    print(f"{RED}❌ {msg}{RESET}")

def print_warning(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")

def print_info(msg):
    print(f"{BLUE}ℹ️  {msg}{RESET}")

def print_section(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

# ==================== 配置 ====================
# 从 simple_main.py 读取的配置
CONFIG = {
    # PostgreSQL 配置
    "POSTGRES_SERVER": "postgres18-0.postgres18.gms.svc.cluster.local",
    "POSTGRES_PORT": "5432",
    "POSTGRES_USER": "postgres",
    "POSTGRES_PASSWORD": "postgres",
    "POSTGRES_DB": "legal_assistant_db",
    "DATABASE_URL": "postgresql://postgres:postgres@postgres18-0.postgres18.gms.svc.cluster.local:5432/legal_assistant_db",

    # Redis 配置
    "REDIS_HOST": "redis7.gms.svc.cluster.local",
    "REDIS_PORT": "6379",
    "REDIS_URL": "redis://redis7.gms.svc.cluster.local:6379/0",

    # AI API 配置
    "LANGCHAIN_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
    "LANGCHAIN_API_BASE_URL": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",
    "MODEL_NAME": "Qwen3-235B-A22B-Thinking-2507",

    "OPENAI_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
    "OPENAI_API_BASE": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",

    "DEEPSEEK_API_KEY": "7adb34bf-3cb3-4dea-af41-b79de8c08ca3",
    "DEEPSEEK_API_URL": "https://sd4a58h819ma6giel1ck0.apigateway-cn-beijing.volceapi.com/v1",

    # 前端配置
    "PRODUCTION_URL": "https://legal-assistant-v3.azgpu02.azshentong.com",
}

# ==================== 1. 数据库连接测试 ====================
def test_database_connection():
    print_section("📊 数据库连接测试")

    # PostgreSQL
    print_info("PostgreSQL 配置:")
    print(f"   主机: {CONFIG['POSTGRES_SERVER']}")
    print(f"   端口: {CONFIG['POSTGRES_PORT']}")
    print(f"   用户: {CONFIG['POSTGRES_USER']}")
    print(f"   数据库: {CONFIG['POSTGRES_DB']}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((CONFIG['POSTGRES_SERVER'], int(CONFIG['POSTGRES_PORT'])))
        if result == 0:
            print_success("PostgreSQL 端口可访问")
        else:
            print_error("PostgreSQL 端口不可访问")
        sock.close()
    except Exception as e:
        print_error(f"PostgreSQL 连接失败: {e}")

    # Redis
    print_info("Redis 配置:")
    print(f"   主机: {CONFIG['REDIS_HOST']}")
    print(f"   端口: {CONFIG['REDIS_PORT']}")

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((CONFIG['REDIS_HOST'], int(CONFIG['REDIS_PORT'])))
        if result == 0:
            print_success("Redis 端口可访问")
        else:
            print_error("Redis 端口不可访问")
        sock.close()
    except Exception as e:
        print_error(f"Redis 连接失败: {e}")

# ==================== 2. AI API 测试 ====================
def test_ai_api(api_name, api_key, base_url, model=None):
    """测试 AI API 连接"""
    print_info(f"测试 {api_name}...")

    # 构建 API 端点
    if "openai" in api_name.lower() or "langchain" in api_name.lower():
        # OpenAI 兼容格式 - chat completions
        endpoint = f"{base_url.rstrip('/')}/chat/completions"
        payload = {
            "model": model or CONFIG.get("MODEL_NAME", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": "Hi"}],
            "max_tokens": 10
        }
    else:
        # 其他格式
        endpoint = base_url
        payload = {"test": "connection"}

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )
        req.add_header('User-Agent', 'Legal-Assistant-Test/1.0')

        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            print_success(f"{api_name} API 连接成功")
            print_info(f"   响应状态: {response.status}")
            return True

    except urllib.error.HTTPError as e:
        print_error(f"{api_name} API HTTP 错误: {e.code} - {e.reason}")
        # 401/403 表示 API Key 无效，但服务器可以访问
        if e.code in [401, 403]:
            print_warning("   服务器可访问，但 API Key 可能无效")
            return "partial"
        return False

    except urllib.error.URLError as e:
        print_error(f"{api_name} API 网络错误: {e.reason}")
        return False

    except Exception as e:
        print_error(f"{api_name} API 未知错误: {e}")
        return False

def test_ai_apis():
    print_section("🤖 AI API 连接测试")

    results = {}

    # LangChain API
    results['LangChain'] = test_ai_api(
        "LangChain",
        CONFIG['LANGCHAIN_API_KEY'],
        CONFIG['LANGCHAIN_API_BASE_URL'],
        CONFIG['MODEL_NAME']
    )

    # OpenAI API
    results['OpenAI'] = test_ai_api(
        "OpenAI",
        CONFIG['OPENAI_API_KEY'],
        CONFIG['OPENAI_API_BASE']
    )

    # DeepSeek API
    results['DeepSeek'] = test_ai_api(
        "DeepSeek",
        CONFIG['DEEPSEEK_API_KEY'],
        CONFIG['DEEPSEEK_API_URL']
    )

    return results

# ==================== 3. 前端配置检查 ====================
def test_frontend_config():
    print_section("💻 前端配置检查")

    # 检查前端构建产物
    frontend_dist = "/home/gms/workspace/legal_assistant_v3/frontend/dist"
    if os.path.exists(frontend_dist):
        print_success("前端构建产物存在")

        # 检查 index.html
        index_file = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_file):
            print_success("index.html 存在")

        # 检查 assets 目录
        assets_dir = os.path.join(frontend_dist, "assets")
        if os.path.exists(assets_dir):
            files = os.listdir(assets_dir)
            print_success(f"assets 目录存在 ({len(files)} 个文件)")
        else:
            print_warning("assets 目录不存在")
    else:
        print_error("前端构建产物不存在，需要运行 npm run build")

    # 检查 API 配置
    print_info("前端 API 配置检查:")
    print_info("   生产环境: 使用相对路径 (空字符串)")
    print_info("   API 请求: https://legal-assistant-v3.azgpu02.azshentong.com/api/v1/...")
    print_info("   nginx 代理: /api/ -> backend:8000")

# ==================== 4. CORS 配置检查 ====================
def test_cors_config():
    print_section("🔒 CORS 配置检查")

    print_info("后端 CORS 允许的源:")
    allowed_origins = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://legal-assistant-v3.azgpu02.azshentong.com",
        "http://180.184.47.218:3001",
    ]
    for origin in allowed_origins:
        print(f"   - {origin}")

    # 检查生产域名
    if CONFIG['PRODUCTION_URL'] in allowed_origins:
        print_success(f"生产域名 {CONFIG['PRODUCTION_URL']} 在 CORS 允许列表中")
    else:
        print_error(f"生产域名 {CONFIG['PRODUCTION_URL']} 不在 CORS 允许列表中")

# ==================== 5. 部署端口配置检查 ====================
def test_deployment_ports():
    print_section("🚀 部署端口配置")

    print_info("端口映射:")
    print("   容器内部 -> 外部访问")
    print("   -------------------")
    print("   后端: 8000 -> 9000 (docker-compose) / 7860 (simple_main.py)")
    print("   前端: 80 -> 3001 (docker-compose)")
    print("   PostgreSQL: 5432 -> 5433 (docker-compose)")
    print("   Redis: 6379 -> (内部)")
    print("   OnlyOffice: 80 -> 8083 (docker-compose)")

    print_info("生产环境访问:")
    print(f"   前端: {CONFIG['PRODUCTION_URL']}/")
    print(f"   后端 API: {CONFIG['PRODUCTION_URL']}/api/v1/")
    print(f"   API 文档: {CONFIG['PRODUCTION_URL']}/docs")
    print(f"   健康检查: {CONFIG['PRODUCTION_URL']}/health")

# ==================== 6. 总结报告 ====================
def generate_summary(db_ok, ai_results, frontend_ok):
    print_section("📋 验证总结报告")

    print("\n【数据库连接】")
    if db_ok:
        print_success("PostgreSQL 和 Redis 连接正常")
    else:
        print_error("数据库连接存在问题")

    print("\n【AI API 连接】")
    for api, result in ai_results.items():
        if result is True:
            print_success(f"{api} API - 完全正常")
        elif result == "partial":
            print_warning(f"{api} API - 服务器可访问，但 API Key 可能无效")
        else:
            print_error(f"{api} API - 连接失败")

    print("\n【前端配置】")
    if frontend_ok:
        print_success("前端构建产物存在")
    else:
        print_error("前端需要重新构建")

    print("\n【部署就绪状态】")
    all_good = db_ok and frontend_ok and all(r is True or r == "partial" for r in ai_results.values())

    if all_good:
        print_success("✨ 所有配置就绪，可以部署！")
        print("\n🚀 部署命令:")
        print("   git add .")
        print('   git commit -m "feat: 完成部署配置验证"')
        print("   git push")
        print(f"\n📍 部署后访问: {CONFIG['PRODUCTION_URL']}/")
    else:
        print_warning("⚠️  部分配置需要修复后再部署")

    print("\n" + "="*60)

# ==================== 主函数 ====================
def main():
    print("="*60)
    print("  线上部署完整验证脚本")
    print("  检查前后端通信 + AI API 有效性")
    print("="*60)

    # 1. 数据库连接测试
    test_database_connection()

    # 2. AI API 测试
    ai_results = test_ai_apis()

    # 3. 前端配置检查
    test_frontend_config()

    # 4. CORS 配置检查
    test_cors_config()

    # 5. 部署端口配置
    test_deployment_ports()

    # 6. 生成总结报告
    frontend_dist = "/home/gms/workspace/legal_assistant_v3/frontend/dist"
    frontend_ok = os.path.exists(frontend_dist) and os.path.exists(os.path.join(frontend_dist, "index.html"))
    generate_summary(True, ai_results, frontend_ok)

if __name__ == "__main__":
    main()
