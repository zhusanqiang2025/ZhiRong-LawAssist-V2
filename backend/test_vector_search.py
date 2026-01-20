"""
测试向量检索是否工作
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.contract_generation.rag import get_template_indexer

def main():
    print("=" * 60)
    print("测试向量检索")
    print("=" * 60)

    db = SessionLocal()

    try:
        # 获取索引器
        indexer = get_template_indexer()

        # 测试检索
        print("\n测试 1: 搜索'技术服务合同'")
        print("-" * 40)

        from app.services.contract_generation.rag.vector_store import get_vector_store
        vector_store = get_vector_store()

        results = vector_store.search_templates(
            query_text="技术服务合同",
            top_k=3,
            user_id=None,
            is_public=True
        )

        if results:
            print(f"✓ 找到 {len(results)} 个相关模板:")
            for i, result in enumerate(results, 1):
                print(f"\n  [{i}] {result.metadata.get('name', 'N/A')}")
                print(f"      类别: {result.metadata.get('category', 'N/A')}")
                print(f"      相似度: {result.score:.4f}")
        else:
            print("✗ 未找到相关模板")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    main()
