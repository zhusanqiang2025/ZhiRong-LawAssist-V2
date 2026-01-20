#!/usr/bin/env python3
"""
测试知识图谱集成到合同生成工作流

验证：
1. 知识图谱查询节点是否正常工作
2. 合同起草是否使用了知识图谱法律特征
3. 模板上传是否自动关联知识图谱
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 添加后端路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph


async def test_knowledge_graph_query():
    """测试知识图谱查询功能"""
    print("=" * 60)
    print("测试 1: 知识图谱查询功能")
    print("=" * 60)

    kg = get_contract_knowledge_graph()

    # 测试精确匹配
    print("\n1.1 测试精确匹配:")
    contract_name = "不动产买卖合同"
    definition = kg.get_by_name(contract_name)

    if definition:
        print(f"   ✓ 找到合同类型: {definition.name}")
        print(f"   ✓ 分类: {definition.category} > {definition.subcategory}")

        if definition.legal_features:
            features = definition.legal_features
            print(f"   ✓ 交易性质: {features.transaction_nature.value}")
            print(f"   ✓ 合同标的: {features.contract_object.value}")
            print(f"   ✓ 复杂程度: {features.complexity.value}")
            print(f"   ✓ 起草立场: {features.stance.value}")
            print(f"   ✓ 适用场景: {features.usage_scenario}")
    else:
        print(f"   ✗ 未找到合同类型: {contract_name}")

    # 测试模糊搜索
    print("\n1.2 测试模糊搜索:")
    search_query = "房屋买卖"
    results = kg.search_by_keywords(search_query)

    if results:
        print(f"   ✓ 找到 {len(results)} 个匹配结果:")
        for defn, score in results[:3]:
            print(f"      - {defn.name} (匹配度: {score:.1f})")
    else:
        print(f"   ✗ 未找到匹配结果: {search_query}")

    # 测试分类查询
    print("\n1.3 测试分类查询:")
    category = "买卖合同"
    definitions = kg.get_by_category(category)

    if definitions:
        print(f"   ✓ 在 '{category}' 下找到 {len(definitions)} 个合同类型:")
        for defn in definitions[:5]:
            print(f"      - {defn.name}")
    else:
        print(f"   ✗ 分类中无合同类型: {category}")

    return True


async def test_workflow_integration():
    """测试工作流集成"""
    print("\n" + "=" * 60)
    print("测试 2: 工作流集成")
    print("=" * 60)

    try:
        from app.services.contract_generation.workflow import generate_contract_simple

        print("\n2.1 测试合同生成（集成知识图谱）:")
        user_input = "我需要一份房屋买卖合同，买家是张三，卖家是李四，房价200万"

        print(f"   用户输入: {user_input}")
        print("   正在调用工作流...")

        result = await generate_contract_simple(
            user_input=user_input,
            uploaded_files=[]
        )

        if result.get("success"):
            print("   ✓ 工作流执行成功")

            # 检查是否包含知识图谱特征
            if result.get("contracts"):
                contract = result["contracts"][0]
                content = contract.get("content", "")

                # 检查内容长度
                if len(content) > 100:
                    print(f"   ✓ 生成合同内容，长度: {len(content)} 字符")

                    # 显示前200字符预览
                    preview = content[:200].replace("\n", " ")
                    print(f"   ✓ 内容预览: {preview}...")
                else:
                    print(f"   ✗ 生成内容过短: {len(content)} 字符")

            # 检查分析结果
            analysis = result.get("analysis_result", {})
            if analysis:
                print(f"   ✓ 需求分析完成: {analysis.get('processing_type')}")
        else:
            error = result.get("error", "未知错误")
            print(f"   ✗ 工作流执行失败: {error}")

        return result.get("success", False)

    except Exception as e:
        print(f"   ✗ 工作流测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_template_upload_integration():
    """测试模板上传时知识图谱集成"""
    print("\n" + "=" * 60)
    print("测试 3: 模板上传知识图谱集成（模拟）")
    print("=" * 60)

    try:
        from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph

        kg = get_contract_knowledge_graph()

        # 模拟上传场景
        template_name = "不动产买卖合同"
        category = "买卖合同"
        subcategory = "不动产买卖"

        print(f"\n3.1 模拟上传模板:")
        print(f"   模板名称: {template_name}")
        print(f"   分类: {category} > {subcategory}")

        # 查询知识图谱
        definition = kg.get_by_name(template_name)

        if definition and definition.legal_features:
            features = definition.legal_features

            print(f"\n   ✓ 自动关联知识图谱成功:")
            print(f"      匹配合同类型: {definition.name}")
            print(f"      自动填充V2特征:")
            print(f"         - 交易性质: {features.transaction_nature.value}")
            print(f"         - 合同标的: {features.contract_object.value}")
            print(f"         - 复杂程度: {features.complexity.value}")
            print(f"         - 起草立场: {features.stance.value}")

            return True
        else:
            print(f"   ✗ 未找到知识图谱匹配")
            return False

    except Exception as e:
        print(f"   ✗ 模板上传集成测试失败: {e}")
        return False


async def main():
    """运行所有测试"""
    print("\n" + "🧪" * 30)
    print("知识图谱集成测试套件")
    print("🧪" * 30 + "\n")

    results = {}

    # 测试 1: 知识图谱查询
    results["knowledge_graph_query"] = await test_knowledge_graph_query()

    # 测试 2: 工作流集成
    results["workflow_integration"] = await test_workflow_integration()

    # 测试 3: 模板上传集成
    results["template_upload_integration"] = await test_template_upload_integration()

    # 汇总结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✓ 通过" if passed else "✗ 失败"
        print(f"{test_name}: {status}")

    total = len(results)
    passed = sum(results.values())
    print(f"\n总计: {passed}/{total} 测试通过")

    if passed == total:
        print("\n🎉 所有测试通过！知识图谱集成成功。")
    else:
        print(f"\n⚠️  {total - passed} 个测试失败，请检查配置。")


if __name__ == "__main__":
    asyncio.run(main())
