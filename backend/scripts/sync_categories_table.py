"""
同步 categories 表结构到最新模型

添加缺失字段：
- code: 分类编码
- description: 分类描述
- meta_info: 扩展元数据 (JSON)
"""
import sys
from pathlib import Path

CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import engine
from sqlalchemy import text

print("\n" + "="*80)
print("同步 categories 表结构")
print("="*80 + "\n")

with engine.connect() as conn:
    # 检查现有表结构
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'categories'
        ORDER BY ordinal_position
    """))
    existing_columns = [row[0] for row in result]

    print("现有列:", existing_columns)
    print()

    # 添加缺失的列
    alterations = []

    if 'code' not in existing_columns:
        alterations.append("ADD COLUMN code VARCHAR(50)")
        print("✓ 将添加: code (VARCHAR(50))")

    if 'description' not in existing_columns:
        alterations.append("ADD COLUMN description TEXT")
        print("✓ 将添加: description (TEXT)")

    if 'meta_info' not in existing_columns:
        alterations.append("ADD COLUMN meta_info JSON DEFAULT '{}'")
        print("✓ 将添加: meta_info (JSON)")

    if not alterations:
        print("\n✅ 表结构已是最新，无需修改")
    else:
        print("\n执行表结构修改...")
        for alter_sql in alterations:
            sql = f"ALTER TABLE categories {alter_sql}"
            print(f"  执行: {sql}")
            conn.execute(text(sql))

        conn.commit()
        print("\n✅ 表结构同步完成")

    # 验证结果
    print("\n验证修改后的表结构:")
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_name = 'categories'
        ORDER BY ordinal_position
    """))
    for row in result:
        print(f"  {row[0]}: {row[1]}")

print("\n" + "="*80)
