"""
清空并重建 ChromaDB 索引

强制清空现有索引，然后重新索引所有模板
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
import logging

logging.basicConfig(level=logging.INFO)

print("\n" + "="*100)
print("清空并重建 ChromaDB 索引")
print("="*100 + "\n")

# 获取数据库会话
db = SessionLocal()

try:
    indexer = get_template_indexer()

    # 步骤 1: 清空现有索引
    print("步骤 1: 清空现有 ChromaDB 索引")
    result = indexer.rebuild_index(db)
    print(f"  旧索引已清空")

    # 步骤 2: 重新索引所有公开模板
    print("\n步骤 2: 重新索引所有公开模板")

    templates = db.query(ContractTemplate).filter(
        ContractTemplate.is_public == True,
        ContractTemplate.status == "active"
    ).all()

    print(f"  找到 {len(templates)} 个公开模板")

    # 批量索引
    result = indexer.index_templates_batch(templates, reindex=True)

    print(f"\n  索引完成:")
    print(f"    成功: {result['success']}")
    print(f"    失败: {result['failed']}")
    print(f"    总计: {result['total']}")

    # 步骤 3: 验证结果
    print("\n步骤 3: 验证 ChromaDB 索引结果")

    vector_store = indexer.vector_store
    public_collection = vector_store._get_or_create_collection(is_public=True)
    final_count = public_collection.count()

    print(f"  ChromaDB 公共集合向量数: {final_count}")

    if final_count == len(templates):
        print("  ✅ 所有模板已成功索引")
    else:
        print(f"  ⚠️  索引数量不匹配: 数据库 {len(templates)} vs ChromaDB {final_count}")

    # 步骤 4: 验证V2特征
    print("\n步骤 4: 验证V2特征同步")

    # 抽样检查
    sample_templates = templates[:3]
    for template in sample_templates:
        try:
            result = public_collection.get(
                ids=[template.id],
                include=["metadatas"]
            )

            if result['ids'] and len(result['ids']) > 0:
                metadata = result['metadatas'][0]

                has_v2 = all([
                    metadata.get('transaction_nature'),
                    metadata.get('contract_object'),
                    metadata.get('complexity'),
                    metadata.get('stance')
                ])

                status = "✅" if has_v2 else "❌"
                print(f"  {status} {template.name[:30]}")
                if not has_v2:
                    print(f"       V2: {metadata.get('transaction_nature')}/{metadata.get('contract_object')}")
        except Exception as e:
            print(f"  ❌ {template.name[:30]} - 检查失败: {e}")

    print("\n" + "="*100)
    print("重建完成")
    print("="*100)

finally:
    db.close()
