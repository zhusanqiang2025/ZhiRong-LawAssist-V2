"""
诊断模板索引问题

检查为什么只有部分模板被索引到ChromaDB
"""
import sys
import os
from pathlib import Path

# 添加 backend 目录到 Python 路径
CURRENT_DIR = Path(__file__).parent
BACKEND_DIR = CURRENT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

print("\n" + "="*100)
print("诊断模板索引问题")
print("="*100 + "\n")

# 获取数据库会话
db = SessionLocal()

try:
    # 获取所有公开模板
    templates = db.query(ContractTemplate).filter(
        ContractTemplate.is_public == True
    ).all()

    print(f"数据库中的公开模板总数: {len(templates)}\n")

    # 统计文件情况
    files_exist = 0
    files_missing = 0
    files_markdown = 0
    files_other = 0

    missing_files = []

    for t in templates:
        file_path = t.file_url
        file_exists = os.path.exists(file_path)

        if file_exists:
            files_exist += 1
            file_ext = Path(file_path).suffix.lower()
            if file_ext in ['.md', '.markdown']:
                files_markdown += 1
            else:
                files_other += 1
        else:
            files_missing += 1
            missing_files.append({
                'name': t.name,
                'path': file_path,
                'id': t.id
            })

    print("文件存在性检查:")
    print(f"  文件存在: {files_exist}")
    print(f"  文件缺失: {files_missing}")
    print(f"  Markdown文件: {files_markdown}")
    print(f"  其他格式文件: {files_other}")

    if missing_files:
        print(f"\n❌ 缺失文件列表 (前10个):")
        for f in missing_files[:10]:
            print(f"  - {f['name']}")
            print(f"    路径: {f['path']}")
            print(f"    ID: {f['id']}")

    # 检查文件路径格式
    print(f"\n文件路径格式检查:")
    path_formats = {}
    for t in templates:
        path = t.file_url
        if path.startswith('/app/templates_source/'):
            path_formats['templates_source'] = path_formats.get('templates_source', 0) + 1
        elif path.startswith('/app/storage/templates/'):
            path_formats['storage/templates'] = path_formats.get('storage/templates', 0) + 1
        else:
            path_formats['other'] = path_formats.get('other', 0) + 1

    for format, count in path_formats.items():
        print(f"  {format}: {count}")

    # 分析为什么只有152个被索引
    print(f"\n索引分析:")
    print(f"  数据库记录: {len(templates)}")
    print(f"  可索引的.md文件: {files_markdown}")
    print(f"  ChromaDB实际索引: 152")
    print(f"  差异: {files_markdown - 152}")

    if files_markdown > 152:
        print(f"\n⚠️  有 {files_markdown - 152} 个.md文件未被索引")
        print(f"  可能原因:")
        print(f"    1. 索引过程中出错被跳过")
        print(f"    2. 文件内容为空或解析失败")
        print(f"    3. 索引脚本只处理了部分文件")

    # 建议
    print(f"\n💡 建议:")
    if files_missing > 0:
        print(f"  1. 修复 {files_missing} 个缺失文件的路径")
    if files_markdown != len(templates):
        print(f"  2. 将非Markdown文件转换为.md格式")
    print(f"  3. 重新运行重建索引脚本")
    print(f"  4. 检查索引日志查看具体错误")

finally:
    db.close()

print("\n" + "="*100)
