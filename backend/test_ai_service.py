#!/usr/bin/env python3
"""
测试 AI 法律特征生成功能
"""
import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from app.services.ai import get_legal_features_generator


async def test_ai_service():
    """测试 AI 服务"""
    print("=" * 60)
    print("测试 AI 法律特征生成服务")
    print("=" * 60)

    # 检查配置
    print("\n1. 检查配置:")
    print(f"   API URL: {os.getenv('QWEN3_THINKING_API_URL')}")
    print(f"   Model: {os.getenv('QWEN3_THINKING_MODEL')}")
    print(f"   API Key: {'已配置' if os.getenv('QWEN3_THINKING_API_KEY') else '未配置'}")

    # 获取生成器
    generator = get_legal_features_generator()

    available = generator.is_available()
    print(f"\n2. AI Service Status: {'Available' if available else 'Not Available'}")

    if not available:
        print("\n错误: AI 服务配置不完整，请检查 .env 文件")
        return

    # 测试生成法律特征
    print("\n3. 测试生成法律特征:")
    print("   合同类型: 不动产买卖合同")

    try:
        from app.services.ai import LegalFeaturesPrompt

        prompt = LegalFeaturesPrompt(
            contract_name="不动产买卖合同",
            category="买卖合同",
            subcategory="不动产买卖"
        )

        print("   正在调用 AI 模型...")
        features = await generator.generate_legal_features(prompt)

        print("\n   Generation Result:")
        for key, value in features.items():
            if key == "legal_basis":
                print(f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")

        print("\nTest Passed!")

    except Exception as e:
        print(f"\nTest Failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_ai_service())
