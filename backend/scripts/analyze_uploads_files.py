"""
分析 storage/uploads 目录下的文件使用情况

使用方法：
    docker-compose exec backend python scripts/analyze_uploads_files.py
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
print("分析 storage/uploads 目录下的文件使用情况")
print("="*100 + "\n")

# 获取数据库会话
db = SessionLocal()

# 扫描 storage/uploads 目录
print("步骤 1: 扫描 storage/uploads 目录")
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

# 查询数据库中引用的文件路径
print("\n步骤 2: 查询数据库中引用的文件路径")

# ContractDoc 表中的三个文件路径字段
contracts = db.query(ContractDoc).all()

db_files = set()

# 收集 original_file_path
for c in contracts:
    if c.original_file_path:
        # 提取文件名
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

# 找出孤立文件
print("\n步骤 3: 识别孤立文件")
all_file_names = set(os.path.basename(f) for f in all_files)
orphan_files = all_file_names - db_files

print(f"  孤立文件数: {len(orphan_files)}")
print(f"  已引用文件数: {len(all_file_names) - len(orphan_files)}")

if len(orphan_files) == 0:
    print("  ✅ 没有发现孤立文件，所有文件都被数据库引用")
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

# 显示文件类型统计
print("\n步骤 4: 文件类型统计")
file_types = {}
for file_path in orphan_file_paths:
    ext = os.path.splitext(file_path)[1].lower()
    file_types[ext] = file_types.get(ext, 0) + 1

print(f"  孤立文件类型分布:")
for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
    print(f"    {ext or '(无扩展名)'}: {count} 个")

# 显示前20个孤立文件
print("\n步骤 5: 孤立文件列表（前20个）")
print("  " + "-"*98)
for f in orphan_file_paths[:20]:
    size_kb = os.path.getsize(f) / 1024
    print(f"  - {os.path.basename(f)} ({size_kb:.1f} KB)")

if len(orphan_file_paths) > 20:
    print(f"  ... 还有 {len(orphan_file_paths) - 20} 个文件未显示")

print("\n" + "="*100)
print(f"分析完成: 共 {len(orphan_file_paths)} 个孤立文件 ({size_mb:.2f} MB)")
print("="*100)
print("\n💡 提示: 运行 cleanup_orphan_uploads.py 来删除这些孤立文件")

db.close()
