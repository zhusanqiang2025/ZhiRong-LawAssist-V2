#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSON 规则迁移到数据库脚本

将 review_rules.json 中的规则导入到数据库的 contract_review_rules 表中
替换原有的数据库规则

用法：
1. 在 Docker 容器内运行: docker exec -it <backend_container> python migrate_json_rules_to_db_docker.py
2. 或通过 API 端点触发迁移
"""

import sys
import os
import json

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.rule import ReviewRule  # ✅ 从 contract.py 移动到独立的 rule.py
from datetime import datetime


def load_json_rules():
    """加载 JSON 规则文件"""
    # 规则文件路径 (在 backend 的 config 文件夹中)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    rule_file_path = os.path.join(current_dir, "config", "review_rules.json")

    if not os.path.exists(rule_file_path):
        print(f"错误：规则文件不存在: {rule_file_path}")
        return None

    with open(rule_file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def clear_existing_system_rules(db):
    """清除现有的系统规则"""
    existing_count = db.query(ReviewRule).filter(ReviewRule.is_system == True).count()
    if existing_count > 0:
        print(f"发现 {existing_count} 条现有系统规则，正在删除...")
        db.query(ReviewRule).filter(ReviewRule.is_system == True).delete()
        db.commit()
        print("现有系统规则已清除")
    else:
        print("未发现现有系统规则")


def migrate_universal_rules(db, rules_data):
    """迁移通用规则"""
    universal_rules = rules_data.get("universal_rules", {}).get("rules", [])
    created_count = 0

    for rule in universal_rules:
        # 检查是否已存在同名规则
        existing = db.query(ReviewRule).filter(
            ReviewRule.name == f"[通用] {rule['id']}"
        ).first()

        if existing:
            print(f"跳过已存在的通用规则: {rule['id']}")
            continue

        new_rule = ReviewRule(
            name=f"[通用] {rule['id']}",
            description=f"{rule['category']} - {rules_data['universal_rules']['description']}",
            content=rule['instruction'],
            rule_category="universal",
            priority=10 + int(rule['id'][1:]),  # U01 -> 11, U02 -> 12
            is_system=True,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.add(new_rule)
        created_count += 1
        print(f"创建通用规则: {rule['id']} - {rule['category']}")

    return created_count


def migrate_feature_rules(db, rules_data):
    """迁移特征规则"""
    feature_rules = rules_data.get("feature_rules", {})
    created_count = 0
    priority = 100

    # 遍历特征类型（交易性质、合同标的）
    for feature_type, feature_values in feature_rules.items():
        if feature_type == "description":
            continue

        # 遍历特征值
        for feature_value, rules in feature_values.items():
            for idx, rule in enumerate(rules):
                rule_name = f"[{feature_type}] {feature_value} - {rule['focus']}"
                rule_desc = f"{feature_type}为'{feature_value}'时的{rule['focus']}审查要点"

                # 检查是否已存在
                existing = db.query(ReviewRule).filter(
                    ReviewRule.name == rule_name
                ).first()

                if existing:
                    print(f"跳过已存在的特征规则: {rule_name}")
                    continue

                # 构建 content
                content = f"**{feature_type}**: {feature_value}\n"
                content += f"**关注点**: {rule['focus']}\n"
                content += f"**审查指令**: {rule['instruction']}"

                new_rule = ReviewRule(
                    name=rule_name,
                    description=rule_desc,
                    content=content,
                    rule_category="feature",
                    priority=priority,
                    is_system=True,
                    is_active=True,
                    created_at=datetime.utcnow()
                )
                db.add(new_rule)
                created_count += 1
                priority += 1
                print(f"创建特征规则: {rule_name}")

    return created_count


def migrate_stance_rules(db, rules_data):
    """迁移立场规则"""
    stance_rules = rules_data.get("stance_rules", {})
    created_count = 0
    priority = 200

    # 遍历立场（party_a, party_b）
    for party, party_data in stance_rules.items():
        if party == "description":
            continue

        role_definition = party_data.get("role_definition", "")
        rules = party_data.get("rules", [])

        for rule in rules:
            rule_name = f"[立场-{party}] {rule['focus']}"
            rule_desc = f"{role_definition}的{rule['focus']}审查要点"

            # 检查是否已存在
            existing = db.query(ReviewRule).filter(
                ReviewRule.name == rule_name
            ).first()

            if existing:
                print(f"跳过已存在的立场规则: {rule_name}")
                continue

            # 构建 content
            content = f"**立场**: {party}\n"
            content += f"**角色定义**: {role_definition}\n"
            content += f"**关注点**: {rule['focus']}\n"
            content += f"**审查指令**: {rule['instruction']}"

            new_rule = ReviewRule(
                name=rule_name,
                description=rule_desc,
                content=content,
                rule_category="stance",
                priority=priority,
                is_system=True,
                is_active=True,
                created_at=datetime.utcnow()
            )
            db.add(new_rule)
            created_count += 1
            priority += 1
            print(f"创建立场规则: {rule_name}")

    return created_count


def main():
    """主函数"""
    print("=" * 60)
    print("JSON 规则迁移到数据库")
    print("=" * 60)

    # 加载 JSON 规则
    print("\n1. 加载 JSON 规则文件...")
    rules_data = load_json_rules()
    if not rules_data:
        print("失败：无法加载规则文件")
        return

    print(f"成功加载规则版本: {rules_data.get('version')}")
    print(f"规则描述: {rules_data.get('description')}")

    # 创建数据库会话
    db = SessionLocal()

    try:
        # 清除现有系统规则
        print("\n2. 清除现有系统规则...")
        clear_existing_system_rules(db)

        # 迁移各类规则
        print("\n3. 开始迁移规则...")

        universal_count = migrate_universal_rules(db, rules_data)
        print(f"   通用规则: 创建 {universal_count} 条")

        feature_count = migrate_feature_rules(db, rules_data)
        print(f"   特征规则: 创建 {feature_count} 条")

        stance_count = migrate_stance_rules(db, rules_data)
        print(f"   立场规则: 创建 {stance_count} 条")

        # 提交事务
        db.commit()

        total_count = universal_count + feature_count + stance_count

        print("\n" + "=" * 60)
        print(f"迁移完成！共创建 {total_count} 条系统规则")
        print("=" * 60)

        # 显示统计
        print("\n数据库规则统计:")
        total_rules = db.query(ReviewRule).count()
        system_rules = db.query(ReviewRule).filter(ReviewRule.is_system == True).count()
        custom_rules = db.query(ReviewRule).filter(ReviewRule.is_system == False).count()
        print(f"  总规则数: {total_rules}")
        print(f"  系统规则: {system_rules}")
        print(f"  自定义规则: {custom_rules}")

        # 按类别统计
        print("\n按类别统计:")
        categories = db.query(ReviewRule.rule_category).distinct().all()
        for (cat,) in categories:
            count = db.query(ReviewRule).filter(
                ReviewRule.rule_category == cat,
                ReviewRule.is_system == True
            ).count()
            print(f"  {cat}: {count} 条")

    except Exception as e:
        print(f"\n错误: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    main()
