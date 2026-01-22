#!/usr/bin/env python3
"""
前后端通信验证脚本

用于检查项目的前后端通信配置是否正确。
"""
import os
import sys
import subprocess
import json
from pathlib import Path
from typing import Dict, List, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent


def print_section(title: str):
    """打印分节标题"""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def check_docker_compose() -> Tuple[bool, List[str]]:
    """检查 docker-compose 配置"""
    print("\n📦 检查 Docker Compose 配置...")

    compose_file = PROJECT_ROOT / "docker-compose.yml"
    if not compose_file.exists():
        return False, ["❌ docker-compose.yml 文件不存在"]

    issues = []

    # 读取并检查配置
    content = compose_file.read_text()

    # 检查网络配置
    if "app-network:" not in content:
        issues.append("❌ 缺少 app-network 网络配置")
    else:
        print("✅ app-network 网络配置存在")

    # 检查服务是否在同一网络
    services_in_network = []
    for line in content.split('\n'):
        if line.strip().startswith("networks:") or line.strip().startswith("- app-network"):
            continue
        if "- app-network" in line:
            services_in_network.append("✓")

    if len(services_in_network) > 0:
        print(f"✅ {len(services_in_network)} 个服务配置在 app-network")

    # 检查 nginx 代理配置
    print("\n🌐 检查 Nginx 代理配置...")
    nginx_conf = PROJECT_ROOT / "frontend" / "nginx.conf"
    if nginx_conf.exists():
        conf_content = nginx_conf.read_text()

        if "location /api/" in conf_content:
            print("✅ Nginx /api/ 代理配置存在")
            if "proxy_pass http://backend:8000" in conf_content:
                print("✅ Nginx 正确代理到 backend:8000")
            else:
                issues.append("❌ Nginx 代理目标不正确")
        else:
            issues.append("❌ Nginx 缺少 /api/ 代理配置")

        if "proxy_http_version 1.1" in conf_content:
            print("✅ Nginx HTTP/1.1 配置存在")

        if "proxy_set_header Upgrade" in conf_content:
            print("✅ Nginx WebSocket 支持已配置")
    else:
        issues.append("❌ nginx.conf 文件不存在")

    # 检查前端构建配置
    print("\n🔨 检查前端构建配置...")

    # 检查 VITE_API_BASE_URL 配置
    if "VITE_API_BASE_URL=${VITE_API_BASE_URL:-}" in content or \
       'VITE_API_BASE_URL=${VITE_API_BASE_URL:-""}' in content:
        print("✅ VITE_API_BASE_URL 配置为空字符串（相对路径）- 正确")
    elif "VITE_API_BASE_URL=${VITE_API_BASE_URL:-http://localhost:9000}" in content:
        issues.append("⚠️  VITE_API_BASE_URL 使用 http://localhost:9000 - 生产环境应使用相对路径")

    # 检查 VITE_ONLYOFFICE_URL
    if "legal-assistant-v3.azgpu02.azshentong.com/onlyoffice" in content:
        print("✅ VITE_ONLYOFFICE_URL 配置为生产域名 - 正确")

    return len(issues) == 0, issues


def check_backend_cors() -> Tuple[bool, List[str]]:
    """检查后端 CORS 配置"""
    print("\n🔒 检查后端 CORS 配置...")

    main_file = PROJECT_ROOT / "backend" / "app" / "main.py"
    if not main_file.exists():
        return False, ["❌ backend/app/main.py 文件不存在"]

    content = main_file.read_text()

    issues = []

    # 检查 CORS 中间件
    if "CORSMiddleware" not in content:
        issues.append("❌ 未配置 CORS 中间件")
    else:
        print("✅ CORS 中间件已配置")

    # 检查生产域名是否在允许列表中
    if "https://legal-assistant-v3.azgpu02.azshentong.com" in content:
        print("✅ 生产域名在 CORS 允许列表中")
    else:
        issues.append("❌ 生产域名不在 CORS 允许列表中")

    # 检查是否允许凭证
    if "allow_credentials=True" in content:
        print("✅ CORS 允许发送凭证 (allow_credentials=True)")

    # 检查允许的方法
    if '"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"' in content or \
       '["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]' in content:
        print("✅ CORS 允许完整的 HTTP 方法")

    # 检查 API 路由
    print("\n🛣️  检查 API 路由配置...")
    if 'prefix="/api/v1"' in content:
        print("✅ API 统一路由前缀: /api/v1")

    return len(issues) == 0, issues


def check_frontend_api_config() -> Tuple[bool, List[str]]:
    """检查前端 API 配置"""
    print("\n💻 检查前端 API 配置...")

    api_config_file = PROJECT_ROOT / "frontend" / "src" / "utils" / "apiConfig.ts"
    if not api_config_file.exists():
        return False, ["❌ frontend/src/utils/apiConfig.ts 文件不存在"]

    content = api_config_file.read_text()

    issues = []

    # 检查 API URL 逻辑
    if "import.meta.env.PROD" in content:
        print("✅ API 配置区分开发/生产环境")

    if "return ''" in content or "return '' " in content:
        print("✅ 生产环境返回空字符串（相对路径）- 正确")

    if "return 'http://localhost:8000'" in content:
        print("✅ 开发环境返回 http://localhost:8000")

    # 检查 axios 配置
    api_index_file = PROJECT_ROOT / "frontend" / "src" / "api" / "index.ts"
    if api_index_file.exists():
        api_content = api_index_file.read_text()

        if 'baseURL: getApiBaseUrl() + "/api/v1"' in api_content:
            print("✅ Axios baseURL 配置: getApiBaseUrl() + '/api/v1'")
        else:
            issues.append("❌ Axios baseURL 配置不正确")
    else:
        issues.append("❌ frontend/src/api/index.ts 文件不存在")

    return len(issues) == 0, issues


def check_dockerfile_env() -> Tuple[bool, List[str]]:
    """检查 Dockerfile 环境变量"""
    print("\n🐳 检查 Dockerfile 环境变量...")

    dockerfile = PROJECT_ROOT / "backend" / "Dockerfile"
    if not dockerfile.exists():
        return False, ["❌ backend/Dockerfile 文件不存在"]

    content = dockerfile.read_text()

    issues = []

    # 检查关键环境变量
    env_vars = {
        "LANGCHAIN_API_KEY": "AI 模型 API 密钥",
        "LANGCHAIN_API_BASE_URL": "AI 模型 API 地址",
        "MODEL_NAME": "AI 模型名称",
        "DATABASE_URL": "数据库连接 URL",
        "REDIS_URL": "Redis 连接 URL",
    }

    for var_name, desc in env_vars.items():
        if f"ENV {var_name}" in content:
            value_start = content.find(f"ENV {var_name}")
            value_end = content.find("\n", value_start)
            value = content[value_start:value_end].strip()
            if "=" in value:
                actual_value = value.split("=", 1)[1].strip()
                if actual_value and actual_value not in ["your-api-key-here", "your-openai-api-key-here"]:
                    print(f"✅ {desc} ({var_name}) 已配置")
                else:
                    issues.append(f"⚠️  {desc} ({var_name}) 仍为占位符")
            else:
                print(f"✅ {desc} ({var_name}) 已配置")
        else:
            issues.append(f"❌ 缺少 {desc} ({var_name})")

    return len(issues) == 0, issues


def create_deployment_summary():
    """创建部署配置摘要"""
    print_section("📋 部署配置摘要")

    summary = {
        "production_url": "https://legal-assistant-v3.azgpu02.azshentong.com",
        "architecture": {
            "description": "前后端分离 + nginx 反向代理",
            "services": {
                "frontend": {
                    "container": "legal_assistant_v3_frontend",
                    "image": "nginx:alpine",
                    "internal_port": 80,
                    "external_port": 3001,
                    "technology": "React 18 + TypeScript + Vite",
                    "api_access": "通过 nginx 反向代理到后端"
                },
                "backend": {
                    "container": "legal_assistant_v3_backend",
                    "image": "python:3.11-slim",
                    "internal_port": 8000,
                    "external_port": 9000,
                    "technology": "FastAPI + Python 3.11",
                    "api_route": "/api/v1"
                },
                "database": {
                    "container": "legal_assistant_v3_db",
                    "image": "pgvector/pgvector:pg15",
                    "internal_port": 5432,
                    "external_port": 5433
                },
                "redis": {
                    "container": "legal_assistant_v3_redis",
                    "image": "redis:7-alpine",
                    "internal_port": 6379
                },
                "onlyoffice": {
                    "container": "legal_assistant_v3_onlyoffice",
                    "image": "onlyoffice/documentserver:latest",
                    "internal_port": 80,
                    "external_port": 8083
                }
            },
            "network": {
                "name": "app-network",
                "driver": "bridge"
            }
        },
        "api_communication": {
            "description": "前端通过 nginx 代理访问后端 API",
            "flow": [
                "前端 → https://legal-assistant-v3.azgpu02.azshentong.com/api/v1/...",
                "Nginx → http://backend:8000/api/v1/... (容器内通信)",
                "后端 FastAPI 处理请求并返回"
            ],
            "cors_configured": True,
            "websocket_supported": True
        },
        "deployment_commands": {
            "build": [
                "docker-compose build backend",
                "docker-compose build frontend"
            ],
            "start": [
                "docker-compose up -d"
            ],
            "stop": [
                "docker-compose down"
            ],
            "view_logs": [
                "docker-compose logs -f backend",
                "docker-compose logs -f frontend"
            ]
        }
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main():
    """主函数"""
    print_section("🔍 前后端通信配置检查工具")

    all_passed = True
    all_issues = []

    # 检查 docker-compose
    passed, issues = check_docker_compose()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 检查后端 CORS
    passed, issues = check_backend_cors()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 检查前端 API 配置
    passed, issues = check_frontend_api_config()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 检查 Dockerfile 环境变量
    passed, issues = check_dockerfile_env()
    all_passed = all_passed and passed
    all_issues.extend(issues)

    # 创建部署摘要
    create_deployment_summary()

    # 总结
    print_section("📊 检查结果总结")

    if all_passed:
        print("✅ 所有配置检查通过！前后端通信配置正确。")
        print("\n🚀 可以执行以下命令部署：")
        print("   docker-compose build backend")
        print("   docker-compose build frontend")
        print("   docker-compose up -d")
    else:
        print("❌ 发现配置问题，需要修复：")
        for issue in all_issues:
            print(f"   {issue}")

    print()


if __name__ == "__main__":
    main()
