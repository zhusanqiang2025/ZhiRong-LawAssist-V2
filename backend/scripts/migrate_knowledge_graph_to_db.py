"""
将知识图谱从 JSON 文件迁移到数据库

读取 knowledge_graph_data.json 并将数据导入到 contract_knowledge_types 表
"""
import sys
import os
import json

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

from app.database import SessionLocal
from app.models.contract_knowledge import ContractKnowledgeType


def migrate_knowledge_graph():
    """迁移知识图谱数据到数据库"""
    db = SessionLocal()

    try:
        # 读取JSON文件
        json_file = os.path.join(project_root, "backend/app/services/legal_features/knowledge_graph_data.json")

        if not os.path.exists(json_file):
            print(f"❌ JSON文件不存在: {json_file}")
            return False

        print(f"📖 读取JSON文件: {json_file}")
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        contract_types = data.get('contract_types', [])
        total_count = len(contract_types)
        print(f"📊 找到 {total_count} 个合同类型")

        # 迁移数据
        success_count = 0
        skip_count = 0
        error_count = 0

        for idx, item in enumerate(contract_types, 1):
            try:
                name = item.get('name')
                if not name:
                    print(f"⚠️  [{idx}/{total_count}] 跳过：缺少 name 字段")
                    skip_count += 1
                    continue

                # 检查是否已存在
                existing = db.query(ContractKnowledgeType).filter(
                    ContractKnowledgeType.name == name
                ).first()

                if existing:
                    print(f"⏭️  [{idx}/{total_count}] 跳过已存在：{name}")
                    skip_count += 1
                    continue

                features = item.get('legal_features', {})

                knowledge_type = ContractKnowledgeType(
                    name=name,
                    aliases=item.get('aliases', []),
                    category=item.get('category', ''),
                    subcategory=item.get('subcategory', ''),

                    # 法律特征
                    transaction_nature=features.get('transaction_nature'),
                    contract_object=features.get('contract_object'),
                    stance=features.get('stance'),
                    consideration_type=features.get('consideration_type'),
                    consideration_detail=features.get('consideration_detail'),
                    transaction_characteristics=features.get('transaction_characteristics'),
                    usage_scenario=features.get('usage_scenario'),
                    legal_basis=features.get('legal_basis', []),

                    # 扩展字段
                    recommended_template_ids=item.get('recommended_template_ids', []),

                    # 标记为系统预定义
                    is_system=True,
                    is_active=True
                )

                db.add(knowledge_type)
                success_count += 1

                if success_count % 10 == 0:
                    print(f"✅ 已处理 {success_count}/{total_count}...")

            except Exception as e:
                error_count += 1
                print(f"❌ [{idx}/{total_count}] 处理失败 {item.get('name', 'Unknown')}: {e}")

        # 提交事务
        db.commit()

        print(f"\n{'='*50}")
        print(f"📊 迁移完成统计:")
        print(f"  ✅ 成功: {success_count}")
        print(f"  ⏭️  跳过: {skip_count}")
        print(f"  ❌ 失败: {error_count}")
        print(f"  📋 总计: {total_count}")
        print(f"{'='*50}")

        # 验证数据库中的记录数
        db_count = db.query(ContractKnowledgeType).count()
        print(f"\n🔍 数据库中现有记录数: {db_count}")

        return success_count > 0

    except Exception as e:
        db.rollback()
        print(f"\n❌ 迁移失败: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    print("="*50)
    print("知识图谱数据迁移工具")
    print("从 JSON 文件迁移到 PostgreSQL 数据库")
    print("="*50)
    print()

    success = migrate_knowledge_graph()

    if success:
        print("\n🎉 迁移成功！")
        sys.exit(0)
    else:
        print("\n💔 迁移失败！")
        sys.exit(1)
