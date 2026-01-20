#!/usr/bin/env python3
"""
测试 AI 完善单个合同的功能
"""
import asyncio
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.ai import get_legal_features_generator, LegalFeaturesPrompt


async def test_single_enhance():
    """测试单个合同完善"""
    print("=" * 60)
    print("Test AI Single Contract Enhancement")
    print("=" * 60)

    # 检查配置
    print("\n1. Configuration Check:")
    print(f"   API URL: {os.getenv('QWEN3_THINKING_API_URL')}")
    print(f"   Model: {os.getenv('QWEN3_THINKING_MODEL')}")

    generator = get_legal_features_generator()
    print(f"   AI Service: {'Available' if generator.is_available() else 'Not Available'}")

    if not generator.is_available():
        print("\nError: AI service is not configured properly")
        return

    # 获取知识图谱
    from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph
    graph = get_contract_knowledge_graph()

    print(f"\n2. Knowledge Graph Status:")
    print(f"   Total Contract Types: {len(graph._contract_types)}")

    # 获取第一个合同类型
    first_contract = list(graph._contract_types.values())[0]
    print(f"\n3. Testing with: {first_contract.name}")
    print(f"   Category: {first_contract.category}")
    if first_contract.subcategory:
        print(f"   Subcategory: {first_contract.subcategory}")

    # 检查当前状态
    if first_contract.legal_features:
        print(f"\n   Current Features:")
        print(f"   - transaction_nature: {first_contract.legal_features.transaction_nature}")
        print(f"   - contract_object: {first_contract.legal_features.contract_object}")
        print(f"   - characteristics: {first_contract.legal_features.transaction_characteristics}")

    # 生成新的特征
    print(f"\n4. Generating new features...")
    try:
        prompt = LegalFeaturesPrompt(
            contract_name=first_contract.name,
            category=first_contract.category,
            subcategory=first_contract.subcategory
        )

        features = await generator.generate_legal_features(prompt)

        print(f"\n   Generated Features:")
        for key, value in features.items():
            if key == "legal_basis":
                print(f"   {key}: {value}")
            else:
                print(f"   {key}: {value}")

        print(f"\n5. Saving to knowledge graph...")
        from app.services.legal_features.contract_knowledge_graph import (
            TransactionNature, ContractObject, Complexity, Stance, ConsiderationType, ContractLegalFeatures
        )

        first_contract.legal_features = ContractLegalFeatures(
            transaction_nature=TransactionNature(features["transaction_nature"]),
            contract_object=ContractObject(features["contract_object"]),
            complexity=Complexity(features["complexity"]),
            stance=Stance(features["stance"]),
            consideration_type=ConsiderationType(features["consideration_type"]),
            consideration_detail=features["consideration_detail"],
            transaction_characteristics=features["transaction_characteristics"],
            usage_scenario=features["usage_scenario"],
            legal_basis=features.get("legal_basis", [])
        )

        graph.save_to_file()

        print(f"\n   Successfully updated and saved!")

    except Exception as e:
        print(f"\n   Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_single_enhance())
