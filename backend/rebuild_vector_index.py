"""
重建向量索引脚本

将数据库中的所有合同模板索引到向量存储中。
"""
import sys
import os

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
from app.services.contract_generation.rag import get_template_indexer

def rebuild_index():
    """重建所有模板的向量索引"""
    db = SessionLocal()
    indexer = get_template_indexer()

    try:
        # 获取所有公共模板
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.is_public == True
        ).all()

        print(f"找到 {len(templates)} 个公共模板")

        if not templates:
            print("没有找到需要索引的模板")
            return

        # 索引所有模板
        result = indexer.index_all_templates(db, reindex=True)

        print(f"\n索引完成:")
        print(f"  成功: {result['success']}")
        print(f"  失败: {result['failed']}")
        print(f"  总计: {result['total']}")

        if result.get('errors'):
            print("\n错误详情:")
            for error in result['errors'][:5]:  # 只显示前5个
                print(f"  - {error}")

    finally:
        db.close()

if __name__ == "__main__":
    rebuild_index()
