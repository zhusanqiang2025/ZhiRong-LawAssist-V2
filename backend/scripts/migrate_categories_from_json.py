"""
从 categories.json 迁移分类数据到数据库

将 categories.json 的层级结构导入到 categories 表中
"""
import sys
import json
from pathlib import Path

CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.category import Category

print("\n" + "="*80)
print("从 categories.json 迁移数据到数据库")
print("="*80 + "\n")

# 读取 categories.json
json_file = BACKEND_DIR / "categories.json"
with open(json_file, 'r', encoding='utf-8') as f:
    categories_data = json.load(f)

db = SessionLocal()

try:
    # 检查是否已有数据
    existing_count = db.query(Category).count()
    if existing_count > 0:
        print(f"⚠️  数据库中已有 {existing_count} 条分类记录")
        print("自动清空并重新导入...\n")
        db.query(Category).delete()
        db.commit()
        print("已清空现有数据\n")

    # 统计变量
    total_count = 0
    parent_map = {}  # (primary_id, sub_type_name) -> category_id

    # 遍历一级分类
    for primary_cat in categories_data.get("primary_categories", []):
        primary_id = primary_cat.get("id")
        primary_name = primary_cat.get("name")
        primary_desc = primary_cat.get("description", "")

        print(f"处理一级分类: {primary_name}")

        # 创建一级分类
        primary_category = Category(
            name=primary_name,
            code=primary_id,
            description=primary_desc,
            parent_id=None,
            sort_order=int(primary_id) if primary_id.isdigit() else 0,
            meta_info={"level": "primary"},
            is_active=True
        )
        db.add(primary_category)
        db.flush()  # 获取ID

        primary_db_id = primary_category.id
        total_count += 1

        # 遍历二级分类
        for sub_type in primary_cat.get("sub_types", []):
            sub_type_name = sub_type.get("name")
            contract_type = sub_type.get("contract_type", "")
            industry = sub_type.get("industry", "")
            usage_scene = sub_type.get("usage_scene", "")

            print(f"  - 二级分类: {sub_type_name}")

            # 创建二级分类
            sub_category = Category(
                name=sub_type_name,
                code=f"{primary_id}-{sub_type_name[:2]}",
                description=f"{contract_type} - {industry}",
                parent_id=primary_db_id,
                sort_order=0,
                meta_info={
                    "level": "secondary",
                    "contract_type": contract_type,
                    "industry": industry,
                    "usage_scene": usage_scene,
                    "sub_categories": sub_type.get("sub_categories", [])
                },
                is_active=True
            )
            db.add(sub_category)
            db.flush()

            parent_map[(primary_id, sub_type_name)] = sub_category.id
            total_count += 1

            # 遍历三级分类（sub_categories）
            for sub_cat_name in sub_type.get("sub_categories", []):
                print(f"    - 三级分类: {sub_cat_name}")

                tertiary_category = Category(
                    name=sub_cat_name,
                    code=f"{primary_id}-{sub_type_name[:2]}-{sub_cat_name[:2]}",
                    description="",
                    parent_id=sub_category.id,
                    sort_order=0,
                    meta_info={"level": "tertiary"},
                    is_active=True
                )
                db.add(tertiary_category)
                total_count += 1

    db.commit()

    print("\n" + "="*80)
    print(f"✅ 迁移完成！共导入 {total_count} 条分类记录")
    print("="*80)

    # 验证导入结果
    print("\n验证统计:")
    primary_count = db.query(Category).filter(Category.parent_id == None).count()
    all_with_parent = db.query(Category).filter(Category.parent_id != None).all()

    print(f"  一级分类: {primary_count}")
    print(f"  其他分类: {len(all_with_parent)}")

    total_check = db.query(Category).count()
    print(f"  总记录数: {total_check}")

    if total_check == total_count:
        print("\n✅ 数据一致性验证通过")
    else:
        print(f"\n⚠️  数据不一致: 预期 {total_count}, 实际 {total_check}")

finally:
    db.close()

print()
