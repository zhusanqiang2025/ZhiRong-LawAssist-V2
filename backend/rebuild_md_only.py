"""
清空向量索引并重新构建（仅 Markdown 文件）
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
from app.services.contract_generation.rag import get_template_indexer

def main():
    print("=" * 60)
    print("清空向量索引并重新构建（仅 Markdown 文件）")
    print("=" * 60)
    print()

    db = SessionLocal()

    try:
        indexer = get_template_indexer()

        # 1. 清空现有索引
        print("[1/2] 清空现有向量索引...")
        indexer.clear_all_indexed()
        print("✓ 索引已清空")
        print()

        # 2. 获取所有 Markdown 模板
        print("[2/2] 重新索引 Markdown 模板...")

        templates = db.query(ContractTemplate).filter(
            ContractTemplate.is_public == True,
            ContractTemplate.status == "active"
        ).all()

        # 过滤出 Markdown 文件
        md_templates = [t for t in templates if t.file_url and t.file_url.endswith(('.md', '.markdown'))]

        print(f"找到 {len(md_templates)} 个 Markdown 模板（共 {len(templates)} 个模板）")
        print()

        if not md_templates:
            print("没有找到 Markdown 模板")
            return

        # 显示前几个模板
        print("Markdown 模板示例:")
        for t in md_templates[:5]:
            print(f"  - {t.name} ({t.file_url})")

        print()
        print("开始索引...")

        # 批量索引
        result = indexer.index_templates_batch(md_templates, reindex=False)

        print()
        print("=" * 60)
        print("索引完成:")
        print(f"  成功: {result['success']}")
        print(f"  失败: {result['failed']}")
        print(f"  总计: {result['total']}")
        print("=" * 60)

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
