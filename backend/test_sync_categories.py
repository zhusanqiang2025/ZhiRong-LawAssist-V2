#!/usr/bin/env python3
"""
测试知识图谱同步功能
"""
import asyncio
import sys
import os
from dotenv import load_dotenv

load_dotenv()
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.services.legal_features.contract_knowledge_graph import get_contract_knowledge_graph
from app.database import get_db
from app.api.v1.endpoints.categories import get_category_tree


async def test_sync():
    """测试同步功能"""
    print("=" * 60)
    print("知识图谱同步功能测试")
    print("=" * 60)

    db = next(get_db())
    try:
        # 1. 获取分类树
        print("\n1. 获取分类树...")
        tree = await get_category_tree(include_inactive=True, db=db)

        # 转换为字典
        category_tree_dict = [item.model_dump() for item in tree]
        print(f"   ✓ 分类树节点数: {count_nodes(category_tree_dict)}")

        # 2. 获取当前知识图谱状态
        print("\n2. 当前知识图谱状态:")
        kg = get_contract_knowledge_graph()
        old_count = len(kg._contract_types)
        print(f"   当前合同类型数: {old_count}")

        # 3. 执行同步
        print("\n3. 执行同步...")
        added, skipped = kg.sync_from_category_tree(category_tree_dict)

        print(f"   新增: {added}")
        print(f"   跳过: {skipped}")

        # 4. 保存到文件
        print("\n4. 保存到文件...")
        success = kg.save_to_file()
        if success:
            print(f"   ✓ 保存成功")
        else:
            print(f"   ✗ 保存失败")

        # 5. 验证结果
        print("\n5. 验证结果:")
        new_count = len(kg._contract_types)
        print(f"   同步前: {old_count} 个合同类型")
        print(f"   同步后: {new_count} 个合同类型")
        print(f"   实际新增: {new_count - old_count} 个")

        # 6. 显示新增的合同类型
        if added > 0:
            print(f"\n6. 新增的合同类型（前5个）:")
            # 获取所有合同类型名称
            all_names = set(kg._contract_types.keys())
            # 这里我们无法直接知道哪些是新增的，所以只显示总数
            print(f"   共新增 {added} 个合同类型")

            # 显示一些示例
            sample_names = list(kg._contract_types.keys())[:5]
            for name in sample_names:
                defn = kg.get_by_name(name)
                print(f"   - {name} ({defn.category} > {defn.subcategory})")

        print("\n" + "=" * 60)
        if added > 0:
            print(f"✓ 同步成功！新增了 {added} 个合同类型")
        else:
            print("✓ 同步完成，没有新增合同类型（所有分类已存在）")
        print("=" * 60)

    finally:
        db.close()


def count_nodes(nodes):
    """统计节点总数"""
    count = 0
    for node in nodes:
        count += 1
        children = node.get('children', [])
        if children:
            count += count_nodes(children)
    return count


if __name__ == "__main__":
    asyncio.run(test_sync())
