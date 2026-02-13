"""
重建向量索引脚本 - 简化版
直接调用应用服务，避免依赖问题
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("合同模板向量索引重建")
    print("=" * 60)
    print()

    # 检查数据库是否存在
    db_path = "backend.db"
    if not os.path.exists(db_path):
        print(f"错误：数据库文件不存在: {db_path}")
        print("请先运行应用程序导入模板数据")
        return

    print(f"找到数据库: {db_path}")

    # 尝试导入并运行
    try:
        from app.database import SessionLocal
        from app.models.contract_template import ContractTemplate
        from app.services.contract_generation.rag import get_template_indexer

        db = SessionLocal()

        # 获取公共模板数量
        templates = db.query(ContractTemplate).filter(
            ContractTemplate.is_public == True
        ).all()

        print(f"找到 {len(templates)} 个公共模板")

        if not templates:
            print("没有找到需要索引的模板")
            db.close()
            return

        # 显示前几个模板
        print("\n模板示例:")
        for t in templates[:5]:
            print(f"  - {t.name} ({t.category})")

        # 获取索引器并重建
        print("\n开始重建索引...")
        indexer = get_template_indexer()
        result = indexer.index_all_templates(db, reindex=True)

        print(f"\n索引完成:")
        print(f"  成功: {result['success']}")
        print(f"  失败: {result['failed']}")
        print(f"  总计: {result['total']}")

        if result['errors']:
            print(f"\n错误详情:")
            for error in result['errors'][:5]:
                print(f"  - {error}")

        db.close()

    except ImportError as e:
        print(f"\n错误：缺少依赖包")
        print(f"详细信息: {e}")
        print("\n解决方案：")
        print("1. 确保虚拟环境已激活:")
        print("   .venv\\Scripts\\activate")
        print("\n2. 安装依赖:")
        print("   pip install sqlalchemy fastapi pydantic langchain chromadb")
        print("\n3. 如果 Python 3.14，建议降级到 Python 3.11 或 3.12")

    except Exception as e:
        print(f"\n错误: {str(e)}")
        import traceback
        traceback.print_exc()

    print()
    print("=" * 60)

if __name__ == "__main__":
    main()
    input("\n按 Enter 键退出...")
