#!/usr/bin/env python3
"""
为重新上传的 Word 文档恢复原有的元数据

使用方法：
1. 先运行 extract_metadata_from_markdown.py 生成元数据映射表
2. 上传 Word 文档
3. 运行此脚本为上传的模板恢复元数据
"""
import os
import json
from pathlib import Path
from typing import Dict, Any

# 导入数据库模型
import sys
sys.path.insert(0, '/app')

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

# 元数据映射文件
METADATA_MAPPING_FILE = Path("/app/storage/template_metadata_mapping.json")


def load_metadata_mapping() -> Dict[str, Dict[str, Any]]:
    """加载元数据映射表"""
    if not METADATA_MAPPING_FILE.exists():
        print(f"错误：元数据映射文件不存在 {METADATA_MAPPING_FILE}")
        print("请先运行 extract_metadata_from_markdown.py 生成映射表")
        return {}

    with open(METADATA_MAPPING_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def find_matching_metadata(template_name: str, metadata_mapping: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    根据模板名称查找匹配的元数据

    Args:
        template_name: 模板名称
        metadata_mapping: 元数据映射表

    Returns:
        匹配的元数据，如果没有找到则返回空字典
    """
    # 1. 精确匹配
    if template_name in metadata_mapping:
        return metadata_mapping[template_name]

    # 2. 模糊匹配（包含模板名称）
    for key, metadata in metadata_mapping.items():
        if template_name in key or key in template_name:
            return metadata

    # 3. 未找到
    return {}


def restore_metadata_for_template(
    template: ContractTemplate,
    metadata: Dict[str, Any],
    db: Session
) -> bool:
    """
    为单个模板恢复元数据

    Args:
        template: 模板对象
        metadata: 元数据字典
        db: 数据库会话

    Returns:
        是否成功更新
    """
    if not metadata:
        return False

    try:
        # 更新 metadata_info 字段
        if not template.metadata_info:
            template.metadata_info = {}

        # 保留原有的 legal_features
        existing_features = template.metadata_info.get('legal_features', {})

        # 添加业务元数据
        template.metadata_info.update({
            'original_filename': metadata.get('original_filename', template.file_name),
            'category': metadata.get('category'),
            'type': metadata.get('type'),
            'scenario': metadata.get('scenario'),
            'tags': metadata.get('tags', []),
            'processed_by': metadata.get('processed_by', 'manual_upload'),
            'date': metadata.get('date'),
            'legal_features': existing_features  # 保留 V2 法律特征
        })

        db.commit()
        db.refresh(template)

        return True

    except Exception as e:
        print(f"  ✗ 更新失败: {e}")
        db.rollback()
        return False


def main():
    """主函数"""
    print("=" * 60)
    print("为模板恢复业务元数据")
    print("=" * 60)

    # 加载元数据映射表
    metadata_mapping = load_metadata_mapping()
    if not metadata_mapping:
        return

    print(f"✓ 加载了 {len(metadata_mapping)} 条元数据记录")

    # 连接数据库
    db = SessionLocal()

    try:
        # 获取所有模板
        templates = db.query(ContractTemplate).all()
        print(f"✓ 数据库中有 {len(templates)} 个模板")

        # 统计
        success_count = 0
        not_found_count = 0

        # 为每个模板查找并恢复元数据
        for template in templates:
            print(f"\n处理模板: {template.name}")

            # 查找匹配的元数据
            metadata = find_matching_metadata(template.name, metadata_mapping)

            if metadata:
                print(f"  找到元数据: {metadata.get('type')} / {metadata.get('scenario')}")

                # 恢复元数据
                if restore_metadata_for_template(template, metadata, db):
                    print(f"  ✓ 成功恢复")
                    success_count += 1
            else:
                print(f"  ✗ 未找到匹配的元数据")
                not_found_count += 1

        # 输出统计
        print("\n" + "=" * 60)
        print(f"处理完成：")
        print(f"  - 成功恢复: {success_count} 个模板")
        print(f"  - 未找到元数据: {not_found_count} 个模板")
        print("=" * 60)

    finally:
        db.close()


if __name__ == "__main__":
    main()
