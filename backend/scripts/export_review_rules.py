# -*- coding: utf-8 -*-
"""
合同审查规则导出脚本

功能：
1. 从数据库导出所有审查规则到 JSON 文件
2. 按规则分类组织导出结构
3. 带时间戳命名备份文件

使用方式：
    python backend/scripts/export_review_rules.py
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 Python 路径
current_dir = Path(__file__).parent
backend_dir = current_dir.parent
sys.path.insert(0, str(backend_dir))

# 设置环境变量
os.environ.setdefault("PYTHONPATH", str(backend_dir))

try:
    from app.database import SessionLocal, engine
    from app.models.rule import ReviewRule
except ImportError as e:
    print(f"❌ 导入模块失败: {e}")
    print(f"请确保已安装所需依赖: pip install -r requirements.txt")
    sys.exit(1)


def export_rules_to_json(output_path: str = None) -> dict:
    """
    从数据库导出审查规则到 JSON 文件

    Args:
        output_path: 输出文件路径，默认为 backup/review_rules_export_YYYYMMDD_HHMMSS.json

    Returns:
        导出的规则数据字典
    """
    # 查询所有规则
    with SessionLocal() as db:
        rules = db.query(ReviewRule).order_by(ReviewRule.priority, ReviewRule.id).all()

    # 按分类组织规则
    export_data = {
        "version": "3.0",
        "export_time": datetime.now().isoformat(),
        "total_count": len(rules),
        "description": "合同审查规则数据库导出",
        "universal_rules": {
            "name": "通用底线审查",
            "description": "适用于所有类型合同的微观与形式审查",
            "rules": []
        },
        "feature_rules": {
            "交易性质": {},
            "合同标的": {}
        },
        "stance_rules": {
            "party_a": {
                "role_definition": "甲方 (通常为：买方/发包方/出资方/雇主)",
                "rules": []
            },
            "party_b": {
                "role_definition": "乙方 (通常为：卖方/承包方/受托方/劳动者)",
                "rules": []
            }
        },
        "custom_rules": []
    }

    # 分类处理规则
    for rule in rules:
        rule_dict = {
            "id": f"DB_{rule.id}",
            "name": rule.name,
            "description": rule.description,
            "content": rule.content,
            "priority": rule.priority,
            "is_active": rule.is_active,
            "is_system": rule.is_system,
            "created_at": rule.created_at.isoformat() if rule.created_at else None,
            "creator_id": rule.creator_id
        }

        if rule.rule_category == "universal":
            export_data["universal_rules"]["rules"].append(rule_dict)
        elif rule.rule_category == "feature":
            # 特征规则需要根据特征类型分组
            # 这里简化处理，直接添加到 custom_rules
            export_data["custom_rules"].append(rule_dict)
        elif rule.rule_category == "stance":
            if rule.name and "甲方" in rule.name or "买方" in rule.name:
                export_data["stance_rules"]["party_a"]["rules"].append(rule_dict)
            elif rule.name and "乙方" in rule.name or "卖方" in rule.name:
                export_data["stance_rules"]["party_b"]["rules"].append(rule_dict)
            else:
                export_data["custom_rules"].append(rule_dict)
        else:
            export_data["custom_rules"].append(rule_dict)

    # 确定输出路径
    if output_path is None:
        # 默认输出到 backup 目录
        backup_dir = Path(__file__).parent.parent.parent / "backup"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(backup_dir / f"review_rules_export_{timestamp}.json")

    # 写入文件
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(export_data, f, ensure_ascii=False, indent=2)

    print(f"✅ 规则已导出到: {output_path}")
    print(f"📊 导出统计:")
    print(f"   - 通用规则: {len(export_data['universal_rules']['rules'])} 条")
    print(f"   - 甲方规则: {len(export_data['stance_rules']['party_a']['rules'])} 条")
    print(f"   - 乙方规则: {len(export_data['stance_rules']['party_b']['rules'])} 条")
    print(f"   - 自定义规则: {len(export_data['custom_rules'])} 条")
    print(f"   - 总计: {export_data['total_count']} 条")

    return export_data


def main():
    """主函数"""
    print("=" * 50)
    print("合同审查规则导出工具")
    print("=" * 50)

    # 检查数据库连接
    try:
        with SessionLocal() as db:
            rule_count = db.query(ReviewRule).count()
            print(f"📋 数据库中共有 {rule_count} 条规则")
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return

    # 导出规则
    try:
        export_rules_to_json()
    except Exception as e:
        print(f"❌ 导出失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
