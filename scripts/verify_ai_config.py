#!/usr/bin/env python3
"""
AI 模型 API 配置验证脚本

用于检查项目的 AI 模型 API 配置是否正确。
支持检测：LangChain API、OpenAI API、DeepSeek API
"""
import os
import sys
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "backend"))


def check_env_file() -> Tuple[bool, str]:
    """检查 .env 文件是否存在"""
    env_file = project_root / ".env"
    if env_file.exists():
        return True, f"✅ .env 文件存在: {env_file}"
    return False, f"❌ .env 文件不存在！请从 .env.example 或 .env.production.example 复制配置"


def check_api_key(key_name: str, key_value: str) -> Tuple[bool, str]:
    """检查 API 密钥是否配置"""
    if not key_value:
        return False, f"❌ {key_name} 未配置"
    if key_value in ["your-api-key-here", "your-openai-api-key-here", "your-deepseek-api-key-here"]:
        return False, f"❌ {key_name} 仍为占位符，请填入真实 API 密钥"
    return True, f"✅ {key_name} 已配置 (长度: {len(key_value)} 字符)"


def check_api_url(url_name: str, url_value: str) -> Tuple[bool, str]:
    """检查 API URL 是否配置"""
    if not url_value:
        return False, f"❌ {url_name} 未配置"
    return True, f"✅ {url_name}: {url_value}"


async def test_langchain_api() -> Tuple[bool, str]:
    """测试 LangChain API 连接"""
    try:
        from langchain_openai import ChatOpenAI
        from app.core.config import settings

        api_key = settings.LANGCHAIN_API_KEY
        base_url = settings.LANGCHAIN_API_BASE_URL
        model_name = settings.MODEL_NAME

        if not api_key or api_key in ["your-api-key-here"]:
            return False, "❌ LANGCHAIN_API_KEY 未配置或仍为占位符"

        if not base_url:
            return False, "❌ LANGCHAIN_API_BASE_URL 未配置"

        print(f"   测试连接: {base_url} (模型: {model_name})")

        llm = ChatOpenAI(
            model=model_name,
            api_key=api_key,
            base_url=base_url,
            temperature=0,
            max_tokens=10
        )

        # 简单测试调用
        result = await llm.ainvoke("Hello")
        if result:
            return True, f"✅ LangChain API 连接成功: {base_url}"
        return False, "❌ LangChain API 返回空响应"

    except Exception as e:
        return False, f"❌ LangChain API 连接失败: {str(e)[:100]}"


async def test_openai_api() -> Tuple[bool, str]:
    """测试 OpenAI API 连接"""
    try:
        from openai import AsyncOpenAI
        from app.core.config import settings

        api_key = settings.OPENAI_API_KEY
        base_url = settings.OPENAI_API_BASE

        if not api_key or api_key in ["your-openai-api-key-here"]:
            return False, "❌ OPENAI_API_KEY 未配置或仍为占位符"

        if not base_url:
            return False, "❌ OPENAI_API_BASE 未配置"

        print(f"   测试连接: {base_url}")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        response = await client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )

        if response.choices:
            return True, f"✅ OpenAI API 连接成功: {base_url}"
        return False, "❌ OpenAI API 返回空响应"

    except Exception as e:
        return False, f"❌ OpenAI API 连接失败: {str(e)[:100]}"


async def test_deepseek_api() -> Tuple[bool, str]:
    """测试 DeepSeek API 连接"""
    try:
        from openai import AsyncOpenAI
        from app.core.config import settings

        api_key = settings.DEEPSEEK_API_KEY
        base_url = getattr(settings, 'DEEPSEEK_API_URL', 'https://api.deepseek.com/v1')

        if not api_key or api_key in ["your-deepseek-api-key-here", "default-api-key-change-in-production"]:
            return False, "❌ DEEPSEEK_API_KEY 未配置或仍为占位符"

        print(f"   测试连接: {base_url}")

        client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url
        )

        response = await client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": "Hello"}],
            max_tokens=10
        )

        if response.choices:
            return True, f"✅ DeepSeek API 连接成功: {base_url}"
        return False, "❌ DeepSeek API 返回空响应"

    except Exception as e:
        return False, f"❌ DeepSeek API 连接失败: {str(e)[:100]}"


async def main():
    """主函数"""
    print("=" * 60)
    print("🔍 AI 模型 API 配置验证工具")
    print("=" * 60)
    print()

    # 1. 检查 .env 文件
    print("📁 检查 .env 文件...")
    env_ok, env_msg = check_env_file()
    print(env_msg)
    print()

    if not env_ok:
        print()
        print("💡 请执行以下步骤创建 .env 文件:")
        print("   1. 复制配置文件: cp .env.production.example .env")
        print("   2. 编辑 .env 文件，填入您的 API 密钥")
        print("   3. 重新运行此脚本")
        return

    # 2. 检查环境变量配置
    print("🔧 检查环境变量配置...")

    # 加载 .env 文件
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    load_dotenv(env_path)

    results = []

    # LangChain API
    langchain_key = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_url = os.getenv("LANGCHAIN_API_BASE_URL", "")
    results.append(check_api_key("LANGCHAIN_API_KEY", langchain_key))
    results.append(check_api_url("LANGCHAIN_API_BASE_URL", langchain_url))

    # OpenAI API
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_url = os.getenv("OPENAI_API_BASE", "")
    results.append(check_api_key("OPENAI_API_KEY", openai_key))
    results.append(check_api_url("OPENAI_API_BASE", openai_url))

    # DeepSeek API
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_url = os.getenv("DEEPSEEK_API_URL", "")
    results.append(check_api_key("DEEPSEEK_API_KEY", deepseek_key))
    results.append(check_api_url("DEEPSEEK_API_URL", deepseek_url))

    for ok, msg in results:
        print(msg)

    print()

    # 3. 测试 API 连接
    print("🌐 测试 API 连接...")
    print()

    # 测试 LangChain API
    print("   [1/3] LangChain API (用于风险评估):")
    langchain_ok, langchain_msg = await test_langchain_api()
    print(f"   {langchain_msg}")
    print()

    # 测试 OpenAI API
    print("   [2/3] OpenAI API (用于合同生成):")
    openai_ok, openai_msg = await test_openai_api()
    print(f"   {openai_msg}")
    print()

    # 测试 DeepSeek API
    print("   [3/3] DeepSeek API (用于智能对话):")
    deepseek_ok, deepseek_msg = await test_deepseek_api()
    print(f"   {deepseek_msg}")
    print()

    # 4. 总结
    print("=" * 60)
    print("📊 验证结果总结:")
    print("=" * 60)

    all_configs_ok = all(r[0] for r in results)
    all_apis_ok = langchain_ok or openai_ok or deepseek_ok

    if all_configs_ok and all_apis_ok:
        print("✅ 配置验证通过！所有 API 已正确配置。")
    elif all_apis_ok:
        print("⚠️  部分 API 配置正确，系统可以运行，但某些功能可能受限。")
    else:
        print("❌ 配置验证失败！请检查 API 密钥配置。")

    print()
    print("💡 提示:")
    print("   - 至少需要配置一个有效的 API 才能使用 AI 功能")
    print("   - LangChain API 用于风险评估、文档预整理等核心功能")
    print("   - OpenAI API 用于合同生成模块")
    print("   - DeepSeek API 用于智能对话功能")
    print()
    print("🔗 常用 AI 服务提供商:")
    print("   - OpenAI: https://api.openai.com/v1")
    print("   - DeepSeek: https://api.deepseek.com/v1")
    print("   - 火山引擎 (需要自行配置 API 地址)")
    print()


if __name__ == "__main__":
    asyncio.run(main())
