"""
验证 V2 四维法律特征同步到 ChromaDB

使用方法：
    docker-compose exec backend python scripts/verify_v2_in_chromadb.py
"""
import sys
import os
from pathlib import Path

# 添加 backend 目录到 Python 路径
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
from app.services.contract_generation.rag import get_template_indexer

print("\n" + "="*100)
print("验证 V2 四维法律特征同步到 ChromaDB")
print("="*100 + "\n")

# 获取数据库会话
db = SessionLocal()

try:
    # 获取索引器
    indexer = get_template_indexer()

    # 步骤 1: 检查数据库中的V2特征
    print("步骤 1: 检查数据库中的V2特征")
    templates = db.query(ContractTemplate).filter(
        ContractTemplate.is_public == True
    ).all()

    print(f"  公开模板总数: {len(templates)}")

    # 统计V2特征完整性
    complete_v2 = 0
    partial_v2 = 0
    no_v2 = 0

    for t in templates:
        has_nature = bool(t.transaction_nature)
        has_object = bool(t.contract_object)
        has_complexity = bool(t.complexity)
        has_stance = bool(t.stance)

        if all([has_nature, has_object, has_complexity, has_stance]):
            complete_v2 += 1
        elif any([has_nature, has_object, has_complexity, has_stance]):
            partial_v2 += 1
        else:
            no_v2 += 1

    print(f"  V2特征完整: {complete_v2}")
    print(f"  V2特征部分: {partial_v2}")
    print(f"  无V2特征: {no_v2}")

    # 步骤 2: 检查ChromaDB集合
    print("\n步骤 2: 检查ChromaDB集合")
    vector_store = indexer.vector_store
    collections = vector_store.list_all_collections()

    print(f"  ChromaDB集合总数: {len(collections)}")
    for col in collections:
        print(f"    - {col['name']}: {col['count']} 个向量")

    # 步骤 3: 抽样验证元数据
    print("\n步骤 3: 抽样验证ChromaDB元数据")

    # 尝试获取公共集合
    try:
        public_collection = vector_store._get_or_create_collection(is_public=True)
        collection_count = public_collection.count()

        print(f"  公共集合向量数: {collection_count}")

        if collection_count > 0:
            # 获取前几个模板的元数据
            sample_size = min(5, collection_count)
            print(f"\n  抽样检查前 {sample_size} 个模板的V2特征:")

            # 从数据库获取对应的模板
            sample_templates = templates[:sample_size]

            for template in sample_templates:
                # 尝试从ChromaDB获取
                try:
                    result = public_collection.get(
                        ids=[template.id],
                        include=["metadatas"]
                    )

                    if result['ids'] and len(result['ids']) > 0:
                        metadata = result['metadatas'][0]

                        # 检查V2特征字段
                        has_v2_in_chroma = all([
                            metadata.get('transaction_nature'),
                            metadata.get('contract_object'),
                            metadata.get('complexity'),
                            metadata.get('stance')
                        ])

                        v2_status = "✅ 完整" if has_v2_in_chroma else "❌ 缺失"

                        print(f"\n    模板: {template.name[:30]}")
                        print(f"      数据库V2: nature={template.transaction_nature}, object={template.contract_object}")
                        print(f"      ChromaDB: {v2_status}")

                        if not has_v2_in_chroma:
                            print(f"        ChromaDB元数据: nature={metadata.get('transaction_nature')}, object={metadata.get('contract_object')}")

                    else:
                        print(f"\n    ❌ 模板: {template.name[:30]} - 未在ChromaDB中找到")

                except Exception as e:
                    print(f"\n    ❌ 模板: {template.name[:30]} - 检查失败: {e}")

        else:
            print("  ⚠️  ChromaDB公共集合为空，需要重建索引")

    except Exception as e:
        print(f"  ❌ 访问ChromaDB失败: {e}")

    # 步骤 4: 统计V2特征分布
    print("\n步骤 4: V2特征分布统计")

    v2_fields = {
        'transaction_nature': {},
        'contract_object': {},
        'complexity': {},
        'stance': {}
    }

    for t in templates:
        for field in v2_fields.keys():
            value = getattr(t, field, None)
            if value:
                v2_fields[field][value] = v2_fields[field].get(value, 0) + 1

    for field, values in v2_fields.items():
        print(f"\n  {field}:")
        for value, count in sorted(values.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    - {value}: {count}")

    # 步骤 5: 总结
    print("\n" + "="*100)
    print("验证总结")
    print("="*100)

    if complete_v2 == len(templates):
        print("✅ 所有模板都有完整的V2特征")
    else:
        print(f"⚠️  {complete_v2}/{len(templates)} 个模板有完整的V2特征")
        print(f"   {partial_v2} 个模板部分缺失V2特征")
        print(f"   {no_v2} 个模板完全缺失V2特征")

    print(f"\n💡 建议:")
    if no_v2 > 0 or partial_v2 > 0:
        print("   1. 在管理员后台完善缺失的V2特征")
        print("   2. 运行 rebuild_vector_index.py 重建索引")
    else:
        print("   V2特征已完整，ChromaDB同步正常")

finally:
    db.close()

print("\n" + "="*100)
