"""
测试向量检索功能
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.services.contract_generation.rag.vector_store import get_vector_store

def main():
    print("=" * 60)
    print("测试向量检索")
    print("=" * 60)

    try:
        # 获取向量存储
        vector_store = get_vector_store()

        # 测试查询
        test_queries = [
            "技术服务合同",
            "借款协议",
            "房屋租赁"
        ]

        for query in test_queries:
            print(f"\n查询: {query}")
            print("-" * 40)

            results = vector_store.search(
                query=query,
                top_k=3,
                user_id=None,
                is_public=True
            )

            if results:
                print(f"✓ 找到 {len(results)} 个相关模板:")
                for i, result in enumerate(results, 1):
                    print(f"\n  [{i}] {result.metadata.get('name', 'N/A')}")
                    print(f"      类别: {result.metadata.get('category', 'N/A')}")
                    print(f"      相似度: {result.similarity:.4f}")
            else:
                print("✗ 未找到相关模板")

        print("\n" + "=" * 60)
        print("测试完成")
        print("=" * 60)

    except Exception as e:
        print(f"错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
