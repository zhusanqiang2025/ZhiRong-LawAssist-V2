#!/usr/bin/env python3
"""
从现有的 Markdown 文件中提取 YAML 元数据，生成元数据映射表

用于在重新上传 Word 文档时，保留原有的业务元数据（scenario、tags、type等）
"""
import os
import re
import yaml
import json
from pathlib import Path
from typing import Dict, List, Any

# Markdown 文件目录（优先使用source目录，因为markdown目录的文件可能是空的）
MARKDOWN_DIR = Path("/app/storage/templates/source")
# 输出文件
OUTPUT_FILE = Path("/app/storage/template_metadata_mapping.json")

def extract_yaml_frontmatter(file_path: Path) -> Dict[str, Any]:
    """
    从 Markdown 文件中提取 YAML Frontmatter

    Args:
        file_path: Markdown 文件路径

    Returns:
        提取的元数据字典
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否有 YAML Frontmatter
        if not content.startswith('---'):
            return {}

        # 找到第二个 ---
        end_match = re.search(r'\n---\s*\n', content)
        if not end_match:
            return {}

        yaml_text = content[4:end_match.start()]

        # 解析 YAML
        metadata = yaml.safe_load(yaml_text) or {}

        return metadata

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return {}

def extract_all_metadata() -> Dict[str, Dict[str, Any]]:
    """
    遍历所有 Markdown 文件，提取元数据

    Returns:
        文件名到元数据的映射
    """
    metadata_mapping = {}

    # 遍历所有 .md 文件
    for md_file in MARKDOWN_DIR.glob("*.md"):
        print(f"Processing: {md_file.name}")

        metadata = extract_yaml_frontmatter(md_file)

        if metadata:
            # 使用原始文件名作为 key
            original_filename = metadata.get('original_filename', md_file.stem)

            # 处理日期类型（转换为字符串）
            date_value = metadata.get('date')
            if hasattr(date_value, 'isoformat'):
                date_value = date_value.isoformat()
            elif date_value:
                date_value = str(date_value)

            metadata_mapping[original_filename] = {
                'category': metadata.get('category'),
                'type': metadata.get('type'),
                'scenario': metadata.get('scenario'),
                'tags': metadata.get('tags', []),
                'processed_by': metadata.get('processed_by'),
                'date': date_value
            }

            print(f"  ✓ Found metadata: {metadata_mapping[original_filename]}")

    return metadata_mapping

def main():
    """主函数"""
    print("=" * 60)
    print("提取 Markdown 文件元数据")
    print("=" * 60)

    if not MARKDOWN_DIR.exists():
        print(f"错误：目录不存在 {MARKDOWN_DIR}")
        return

    # 提取所有元数据
    metadata_mapping = extract_all_metadata()

    # 保存为 JSON
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(metadata_mapping, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print(f"✓ 成功提取 {len(metadata_mapping)} 个文件的元数据")
    print(f"✓ 已保存到: {OUTPUT_FILE}")
    print("=" * 60)

    # 显示统计信息
    print("\n元数据统计：")
    print(f"  - 包含 scenario: {sum(1 for m in metadata_mapping.values() if m.get('scenario'))}")
    print(f"  - 包含 tags: {sum(1 for m in metadata_mapping.values() if m.get('tags'))}")
    print(f"  - 包含 type: {sum(1 for m in metadata_mapping.values() if m.get('type'))}")

if __name__ == "__main__":
    main()
