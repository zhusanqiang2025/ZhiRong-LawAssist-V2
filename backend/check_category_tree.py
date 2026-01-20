#!/usr/bin/env python3
"""
检查合同分类树结构，诊断同步问题
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.api.v1.endpoints.categories import get_category_tree


async def check_category_tree():
    """检查分类树结构"""
    print("=" * 60)
    print("合同分类树结构检查")
    print("=" * 60)

    db = next(get_db())
    try:
        tree = await get_category_tree(include_inactive=True, db=db)

        def print_tree(nodes, level=0):
            """递归打印分类树"""
            for node in nodes:
                indent = "  " * level

                # 获取元信息
                if hasattr(node, 'meta_info') and node.meta_info:
                    meta_level = node.meta_info.level if hasattr(node.meta_info, 'level') else "?"
                else:
                    meta_level = "?"

                # 获取子节点数量
                children_count = len(node.children) if hasattr(node, 'children') and node.children else 0

                # 检查是否已有知识图谱条目
                from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph
                kg = get_contract_knowledge_graph()
                exists = node.name in kg._contract_types

                exists_str = "✓ 已存在" if exists else "✗ 不存在"

                print(f"{indent}[{meta_level}] {node.name} (子节点: {children_count}) - {exists_str}")

                # 递归打印子节点
                if hasattr(node, 'children') and node.children:
                    print_tree(node.children, level + 1)

        print("\n=== 当前分类树结构 ===")
        print_tree(tree)

        # 统计信息
        total_nodes = count_nodes(tree)
        leaf_nodes = count_leaf_nodes(tree)

        print(f"\n=== 统计信息 ===")
        print(f"总节点数: {total_nodes}")
        print(f"叶子节点数: {leaf_nodes}")
        print(f"知识图谱中合同类型数: {len(get_contract_knowledge_graph()._contract_types)}")

    finally:
        db.close()


def count_nodes(nodes):
    """统计节点总数"""
    count = 0
    for node in nodes:
        count += 1
        if hasattr(node, 'children') and node.children:
            count += count_nodes(node.children)
    return count


def count_leaf_nodes(nodes):
    """统计叶子节点数"""
    count = 0
    for node in nodes:
        children = node.children if hasattr(node, 'children') else []
        if not children:
            count += 1
        else:
            count += count_leaf_nodes(children)
    return count


if __name__ == "__main__":
    asyncio.run(check_category_tree())
