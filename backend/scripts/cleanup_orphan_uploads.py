"""
清理 storage/uploads 目录下的孤立文件

使用方法：
    docker-compose exec backend python scripts/cleanup_orphan_uploads.py
"""
import os
import sys
from pathlib import Path

# 添加 backend 目录到 Python 路径
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.contract import ContractDoc

print("\n" + "="*100)
print("清理 storage/uploads 目录下的孤立文件")
print("="*100 + "\n")

# 获取数据库会话
db = SessionLocal()

# 查询数据库中引用的文件路径
print("步骤 1: 查询数据库中引用的文件路径")
contracts = db.query(ContractDoc).all()

db_files = set()

# 收集 original_file_path
for c in contracts:
    if c.original_file_path:
        file_name = os.path.basename(c.original_file_path)
        if "uploads" in c.original_file_path or "storage" in c.original_file_path:
            db_files.add(file_name)

# 收集 pdf_converted_path
for c in contracts:
    if c.pdf_converted_path:
        file_name = os.path.basename(c.pdf_converted_path)
        if "uploads" in c.pdf_converted_path or "storage" in c.pdf_converted_path:
            db_files.add(file_name)

# 收集 final_docx_path
for c in contracts:
    if c.final_docx_path:
        file_name = os.path.basename(c.final_docx_path)
        if "uploads" in c.final_docx_path or "storage" in c.final_docx_path:
            db_files.add(file_name)

print(f"  数据库中引用的 uploads 文件数: {len(db_files)}")

# 扫描 storage/uploads 目录
print("\n步骤 2: 扫描 storage/uploads 目录")
storage_dir = "/app/storage/uploads"

if not os.path.exists(storage_dir):
    print(f"  ❌ 目录不存在: {storage_dir}")
    db.close()
    sys.exit(1)

all_files = []
for root, dirs, files in os.walk(storage_dir):
    for file in files:
        file_path = os.path.join(root, file)
        all_files.append(file_path)

print(f"  目录下共有 {len(all_files)} 个文件")

# 找出孤立文件
print("\n步骤 3: 识别孤立文件")
all_file_names = set(os.path.basename(f) for f in all_files)
orphan_files = all_file_names - db_files

print(f"  孤立文件数: {len(orphan_files)}")

if len(orphan_files) == 0:
    print("  ✅ 没有发现孤立文件，无需清理")
    db.close()
    sys.exit(0)

# 找出完整的孤立文件路径
orphan_file_paths = []
for file_path in all_files:
    if os.path.basename(file_path) in orphan_files:
        orphan_file_paths.append(file_path)

print(f"  完整路径数: {len(orphan_file_paths)}")

# 计算总大小
total_size = sum(os.path.getsize(f) for f in orphan_file_paths)
size_mb = total_size / (1024 * 1024)

print(f"  总大小: {size_mb:.2f} MB")

# 确认删除
print("\n" + "="*100)
print(f"准备删除 {len(orphan_file_paths)} 个孤立文件，总计 {size_mb:.2f} MB")
print("="*100)

print("\n将被删除的文件:")
for f in orphan_file_paths:
    size_kb = os.path.getsize(f) / 1024
    print(f"  - {os.path.basename(f)} ({size_kb:.1f} KB)")

print("\n开始删除...")

# 删除孤立文件
deleted_count = 0
failed_count = 0

for file_path in orphan_file_paths:
    try:
        os.remove(file_path)
        deleted_count += 1
    except Exception as e:
        failed_count += 1
        print(f"  ❌ 删除失败: {os.path.basename(file_path)} - {e}")

print(f"\n✅ 删除完成:")
print(f"  成功删除: {deleted_count} 个文件")
print(f"  删除失败: {failed_count} 个文件")
print(f"  释放空间: {size_mb:.2f} MB")

# 验证清理结果
print("\n步骤 4: 验证清理结果")
remaining_files = []
for root, dirs, files in os.walk(storage_dir):
    for file in files:
        file_path = os.path.join(root, file)
        remaining_files.append(file_path)

print(f"  剩余文件数: {len(remaining_files)}")

if len(remaining_files) > 0:
    print(f"\n  ✅ storage/uploads 目录还剩 {len(remaining_files)} 个文件（全部被数据库引用）")
else:
    print("  ⚠️  storage/uploads 目录已清空")

print("\n" + "="*100)
print("清理完成")
print("="*100)

db.close()
