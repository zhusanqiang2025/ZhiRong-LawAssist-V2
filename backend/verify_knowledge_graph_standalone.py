#!/usr/bin/env python3
"""
验证知识图谱更新结果（独立版本）
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 直接从模块文件导入，绕过 __init__.py
import importlib.util

# 加载 contract_knowledge_graph 模块
spec = importlib.util.spec_from_file_location(
    "contract_knowledge_graph",
    os.path.join(os.path.dirname(__file__), "app", "services", "legal_features", "contract_knowledge_graph.py")
)
ckg_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ckg_module)

get_contract_knowledge_graph = ckg_module.get_contract_knowledge_graph

def verify_knowledge_graph():
    """验证知识图谱"""
    print("=" * 60)
    print("验证知识图谱更新结果")
    print("=" * 60)

    kg = get_contract_knowledge_graph()

    total = len(kg._contract_types)
    print(f"\n总合同类型数: {total}")

    # 按分类统计
    categories = {}
    for name, ct_data in kg._contract_types.items():
        # 支持字典和 dataclass 两种格式
        if hasattr(ct_data, 'get'):
            # 字典格式
            category = ct_data.get('category', '未分类')
        else:
            # dataclass 格式
            category = getattr(ct_data, 'category', '未分类')

        if category not in categories:
            categories[category] = []
        categories[category].append(name)

    print(f"\n按分类统计:")
    for category, contracts in sorted(categories.items()):
        print(f"  {category}: {len(contracts)} 个")

    # 随机抽查几个合同类型的法律特征
    print(f"\n抽查合同类型法律特征:")

    test_contracts = [
        "不动产买卖合同",
        "股权转让协议",
        "劳动合同(固定期限)",
        "软件开发合同",
        "保证合同",
        "劳务协议",
        "AI节能改造",
        "节能效益分享型能源管理合同"
    ]

    for contract_name in test_contracts:
        if contract_name in kg._contract_types:
            ct_data = kg._contract_types[contract_name]

            # 支持字典和 dataclass 两种格式
            if hasattr(ct_data, 'get'):
                # 字典格式
                lf = ct_data.get('legal_features')
            else:
                # dataclass 格式
                lf = getattr(ct_data, 'legal_features', None)

            if lf:
                print(f"\n  {contract_name}:")
                tn = lf.transaction_nature.value if hasattr(lf.transaction_nature, 'value') else str(lf.transaction_nature)
                co = lf.contract_object.value if hasattr(lf.contract_object, 'value') else str(lf.contract_object)
                cplx = lf.complexity.value if hasattr(lf.complexity, 'value') else str(lf.complexity)
                s = lf.stance.value if hasattr(lf.stance, 'value') else str(lf.stance)
                print(f"    交易性质: {tn}")
                print(f"    合同标的: {co}")
                print(f"    复杂程度: {cplx}")
                print(f"    起草立场: {s}")
                print(f"    对价类型: {lf.consideration_type.value}")
                print(f"    对价详情: {lf.consideration_detail}")
                print(f"    交易特征: {lf.transaction_characteristics}")
                print(f"    适用场景: {lf.usage_scenario}")
                print(f"    法律依据: {lf.legal_basis}")
            else:
                print(f"\n  {contract_name}: 无法律特征")
        else:
            print(f"\n  {contract_name}: 未找到")

    print("\n" + "=" * 60)
    print("验证完成")
    print("=" * 60)

if __name__ == "__main__":
    verify_knowledge_graph()
