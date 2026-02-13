#!/usr/bin/env python3
"""
诊断 AI 完善知识图谱功能的问题
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph
from app.services.ai import get_legal_features_generator, LegalFeaturesPrompt


async def diagnose_ai_enhance():
    """诊断 AI 完善功能"""
    print("=" * 60)
    print("AI 完善知识图谱功能诊断")
    print("=" * 60)

    # 1. 检查知识图谱加载
    print("\n1. 检查知识图谱加载:")
    try:
        graph = get_contract_knowledge_graph()
        print(f"   ✓ 知识图谱加载成功")
        print(f"   ✓ 合同类型总数: {len(graph._contract_types)}")

        # 显示前5个合同类型
        print(f"   ✓ 前5个合同类型:")
        for i, name in enumerate(list(graph._contract_types.keys())[:5], 1):
            definition = graph.get_by_name(name)
            has_features = definition.legal_features is not None
            print(f"      {i}. {name} - {'有特征' if has_features else '无特征'}")
            if has_features and definition.legal_features:
                print(f"         - 交易特征: {definition.legal_features.transaction_characteristics[:30]}...")
                print(f"         - 适用场景: {definition.legal_features.usage_scenario[:30]}...")

    except Exception as e:
        print(f"   ✗ 知识图谱加载失败: {e}")
        import traceback
        traceback.print_exc()
        return

    # 2. 检查 AI 服务配置
    print("\n2. 检查 AI 服务配置:")
    generator = get_legal_features_generator()

    print(f"   API URL: {os.getenv('QWEN3_API_BASE')}")
    print(f"   Model: {os.getenv('QWEN3_MODEL')}")
    print(f"   API Key: {'已配置' if os.getenv('QWEN3_API_KEY') else '未配置'}")
    print(f"   AI Service: {'可用' if generator.is_available() else '不可用'}")

    if not generator.is_available():
        print(f"   ✗ AI 服务不可用，请检查配置")
        return

    # 3. 测试单个合同 AI 完善
    print("\n3. 测试单个合同 AI 完善:")

    # 选择第一个有法律特征的合同进行测试
    test_name = list(graph._contract_types.keys())[0]
    definition = graph.get_by_name(test_name)

    print(f"   测试合同: {test_name}")
    print(f"   分类: {definition.category} > {definition.subcategory}")

    try:
        # 创建提示词
        prompt = LegalFeaturesPrompt(
            contract_name=test_name,
            category=definition.category,
            subcategory=definition.subcategory
        )

        print(f"   正在调用 AI 模型...")

        # 调用 AI 生成法律特征
        features = await generator.generate_legal_features(prompt)

        print(f"   ✓ AI 生成成功:")
        for key, value in features.items():
            if key == "legal_basis":
                print(f"      {key}: {value}")
            else:
                print(f"      {key}: {value}")

        # 4. 测试更新知识图谱
        print("\n4. 测试更新知识图谱:")
        try:
            from app.services.legal_features.contract_knowledge_graph import (
                TransactionNature, ContractObject, Complexity, Stance, ConsiderationType,
                ContractLegalFeatures
            )

            # 创建新的法律特征对象
            new_features = ContractLegalFeatures(
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

            # 更新定义
            definition.legal_features = new_features

            print(f"   ✓ 法律特征对象创建成功")

            # 5. 测试保存到文件
            print("\n5. 测试保存到文件:")
            success = graph.save_to_file()

            if success:
                print(f"   ✓ 保存到文件成功")
            else:
                print(f"   ✗ 保存到文件失败")

        except Exception as e:
            print(f"   ✗ 更新知识图谱失败: {e}")
            import traceback
            traceback.print_exc()

    except Exception as e:
        print(f"   ✗ AI 生成失败: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose_ai_enhance())
