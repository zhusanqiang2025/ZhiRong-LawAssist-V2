#!/usr/bin/env python3
"""
查看新增的合同类型
"""
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph


def list_new_contract_types():
    """列出所有合同类型"""
    print("=" * 60)
    print("知识图谱中的所有合同类型")
    print("=" * 60)

    kg = get_contract_knowledge_graph()

    # 按分类分组
    by_category = {}
    for name, definition in kg._contract_types.items():
        cat = definition.category or "未分类"
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append({
            'name': name,
            'subcategory': definition.subcategory or '',
            'has_features': definition.legal_features is not None
        })

    # 按分类排序
    for category in sorted(by_category.keys()):
        contracts = by_category[category]
        print(f"\n【{category}】({len(contracts)} 个)")
        for contract in sorted(contracts, key=lambda x: x['name']):
            features_status = "✓" if contract['has_features'] else "✗"
            print(f"  {features_status} {contract['name']}")
            if contract['subcategory']:
                print(f"      └─ {contract['subcategory']}")

    print(f"\n总计: {len(kg._contract_types)} 个合同类型")


if __name__ == "__main__":
    list_new_contract_types()
