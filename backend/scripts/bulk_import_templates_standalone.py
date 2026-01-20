# backend/scripts/bulk_import_templates_standalone.py
"""
合同模板批量导入脚本 - 独立版本

功能：递归扫描目录，生成导入预览和 SQL 脚本

使用方法：
    cd backend
    python scripts/bulk_import_templates_standalone.py --source "D:\合同管理\合同模板"
"""
import os
import sys
import uuid
import argparse
import json
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# 支持的文件扩展名
SUPPORTED_EXTENSIONS = {'.docx', '.doc', '.pdf'}

# 文件夹名称到分类的映射
CATEGORY_MAPPING: Dict[str, tuple] = {
    "劳动合同": ("劳动人事", "劳动合同"),
    "劳务合同": ("劳动人事", "劳务合同"),
    "保密协议": ("劳动人事", "保密协议"),
    "竞业限制": ("劳动人事", "竞业限制"),
    "货物买卖": ("买卖合同", "货物买卖"),
    "设备买卖": ("买卖合同", "设备买卖"),
    "房屋买卖": ("买卖合同", "房屋买卖"),
    "车辆买卖": ("买卖合同", "车辆买卖"),
    "房屋租赁": ("租赁合同", "房屋租赁"),
    "办公室租赁": ("租赁合同", "办公室租赁"),
    "车辆租赁": ("租赁合同", "车辆租赁"),
    "设备租赁": ("租赁合同", "设备租赁"),
    "服务合同": ("服务合同", None),
    "技术服务": ("服务合同", "技术服务"),
    "咨询服务": ("服务合同", "咨询服务"),
    "建设工程": ("建设工程", None),
    "施工合同": ("建设工程", "施工合同"),
    "知识产权": ("知识产权", None),
    "合伙协议": ("其他", "合伙协议"),
    "股东协议": ("公司治理", "股东协议"),
    "借款合同": ("金融借贷", "借款合同"),
}

DEFAULT_CATEGORY = "其他"
DEFAULT_OWNER_ID = 1  # zhusanqiang@az028.cn

def get_file_extension(file_path: Path) -> str:
    return file_path.suffix.lower()

def is_supported_file(file_path: Path) -> bool:
    return get_file_extension(file_path) in SUPPORTED_EXTENSIONS

def get_category_from_folder(folder_name: str) -> tuple:
    folder_name = folder_name.strip()
    if folder_name in CATEGORY_MAPPING:
        return CATEGORY_MAPPING[folder_name]
    for key, value in CATEGORY_MAPPING.items():
        if key in folder_name or folder_name in key:
            return value
    return (folder_name, None)

def extract_keywords_from_filename(filename: str) -> List[str]:
    name = Path(filename).stem
    for suffix in ["模板", "范本", "样本", "格式", "正式版", "修订版", "简单版", "详细版"]:
        name = name.replace(suffix, "")

    keywords = []
    for sep in ["_", "-", " ", "、", "，"]:
        if sep in name:
            parts = name.split(sep)
            keywords.extend([p for p in parts if len(p) >= 2])
            break

    if not keywords:
        i = 0
        while i < len(name):
            for length in [4, 3, 2]:
                if i + length <= len(name):
                    word = name[i:i+length]
                    if len(word) >= 2 and word not in keywords:
                        keywords.append(word)
                    i += length
                    break
            else:
                i += 1

    return [k for k in keywords if len(k) >= 2][:5]

def scan_directory(source_dir: Path, relative_path: str = "") -> List[Dict]:
    files_info = []
    for item in source_dir.iterdir():
        if item.is_file() and is_supported_file(item):
            if relative_path:
                folder_name = relative_path.split(os.sep)[0]
                category, subcategory = get_category_from_folder(folder_name)
            else:
                category, subcategory = DEFAULT_CATEGORY, None

            files_info.append({
                "file_path": str(item),
                "filename": item.name,
                "category": category,
                "subcategory": subcategory,
                "relative_path": relative_path,
            })
        elif item.is_dir():
            subdir_path = os.path.join(relative_path, item.name) if relative_path else item.name
            files_info.extend(scan_directory(item, subdir_path))
    return files_info

def main():
    parser = argparse.ArgumentParser(description="合同模板批量导入工具（独立版本）")
    parser.add_argument("--source", type=str, required=True, help="源目录路径")
    parser.add_argument("--output", type=str, default="import_output", help="输出目录")
    args = parser.parse_args()

    source_dir = Path(args.source)
    if not source_dir.exists():
        print(f"错误: 源目录不存在: {source_dir}")
        return

    print("=" * 60)
    print("合同模板批量导入工具 - 预览模式")
    print("=" * 60)
    print(f"源目录: {source_dir}")
    print("=" * 60)

    # 扫描文件
    print("\n正在扫描文件...")
    files_info = scan_directory(source_dir)

    if not files_info:
        print("未找到任何支持的文件")
        return

    print(f"找到 {len(files_info)} 个文件\n")

    # 统计分类
    category_count = {}
    for fi in files_info:
        cat = f"{fi['category']}/{fi['subcategory'] or '无'}"
        category_count[cat] = category_count.get(cat, 0) + 1

    print("分类统计:")
    for cat, count in sorted(category_count.items()):
        print(f"  {cat}: {count} 个")

    # 生成 JSON 报告
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)

    report = {
        "scan_time": datetime.now().isoformat(),
        "source_directory": str(source_dir),
        "total_files": len(files_info),
        "categories": category_count,
        "files": files_info
    }

    report_path = output_dir / "import_report.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    # 生成 Python 导入脚本
    script_path = output_dir / "execute_import.py"
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write('#!/usr/bin/env python\n')
        f.write('# -*- coding: utf-8 -*-\n')
        f.write('"""执行导入的脚本"""\n\n')
        f.write('import sys\n')
        f.write('import shutil\n')
        f.write('import uuid\n')
        f.write('from pathlib import Path\n')
        f.write('from datetime import datetime\n\n')
        f.write('# 添加项目根目录（从execute_import.py所在目录推导）\n')
        f.write('script_dir = Path(__file__).parent\n')
        f.write('project_root = script_dir.parent  # 假设在 backend/import_output/ 目录\n')
        f.write('sys.path.insert(0, str(project_root))\n\n')
        f.write('from app.database import SessionLocal\n')
        f.write('from app.models.contract_template import ContractTemplate\n\n')
        f.write('SOURCE_DIR = r"{}"\n'.format(source_dir))
        f.write('STORAGE_DIR = "storage/templates"\n')
        f.write('OWNER_ID = {}\n'.format(DEFAULT_OWNER_ID))
        f.write('\n')
        f.write('def main():\n')
        f.write('    db = SessionLocal()\n')
        f.write('    storage_dir = Path(STORAGE_DIR)\n')
        f.write('    storage_dir.mkdir(parents=True, exist_ok=True)\n\n')
        f.write('    templates = [\n')

        for fi in files_info:
            template_id = str(uuid.uuid4())
            keywords = extract_keywords_from_filename(fi['filename'])
            file_ext = get_file_extension(Path(fi['filename']))
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"

            f.write('        {\n')
            f.write('            "id": "{}",\n'.format(template_id))
            f.write('            "name": "{}",\n'.format(Path(fi['filename']).stem))
            f.write('            "category": "{}",\n'.format(fi['category']))
            f.write('            "subcategory": {},\n'.format(f'"{fi["subcategory"]}"' if fi['subcategory'] else 'None'))
            f.write('            "description": "{}",\n'.format(f"{fi['subcategory'] or fi['category']}合同模板"))
            f.write('            "file_name": "{}",\n'.format(fi['filename']))
            f.write('            "file_type": "{}",\n'.format(file_ext[1:]))
            f.write('            "keywords": {},\n'.format(keywords))
            f.write('            "source_path": r"{}",\n'.format(fi['file_path']))
            f.write('            "dest_filename": "{}",\n'.format(unique_filename))
            f.write('        },\n')

        f.write('    ]\n\n')
        f.write('    for t in templates:\n')
        f.write('        try:\n')
        f.write('            # 复制文件\n')
        f.write('            source = Path(t["source_path"])\n')
        f.write('            dest = storage_dir / t["dest_filename"]\n')
        f.write('            shutil.copy2(source, dest)\n')
        f.write('\n')
        f.write('            # 创建数据库记录\n')
        f.write('            template = ContractTemplate(\n')
        f.write('                id=t["id"],\n')
        f.write('                name=t["name"],\n')
        f.write('                category=t["category"],\n')
        f.write('                subcategory=t["subcategory"],\n')
        f.write('                description=t["description"],\n')
        f.write('                file_url=str(dest),\n')
        f.write('                file_name=t["file_name"],\n')
        f.write('                file_size=source.stat().st_size,\n')
        f.write('                file_type=t["file_type"],\n')
        f.write('                is_public=True,\n')
        f.write('                owner_id=OWNER_ID,\n')
        f.write('                keywords=t["keywords"],\n')
        f.write('                status="active",\n')
        f.write('                language="zh-CN",\n')
        f.write('                jurisdiction="中国大陆"\n')
        f.write('            )\n')
        f.write('            db.add(template)\n')
        f.write('            db.commit()\n')
        f.write('            fname = t["file_name"]\n')
        f.write('            print(f"已导入: {fname}")\n')
        f.write('        except Exception as e:\n')
        f.write('            fname = t["file_name"]\n')
        f.write('            print(f"失败 {fname}: {e}")\n')
        f.write('            db.rollback()\n')
        f.write('\n')
        f.write('    db.close()\n')
        f.write('    print("\\n导入完成!")\n\n')
        f.write('if __name__ == "__main__":\n')
        f.write('    main()\n')

    print(f"\n输出文件:")
    print(f"  - 报告: {report_path}")
    print(f"  - 执行脚本: {script_path}")
    print(f"\n下一步: 运行 python {script_path} 执行导入")

if __name__ == "__main__":
    main()
