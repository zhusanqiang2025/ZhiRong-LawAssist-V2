#!/usr/bin/env python3
"""
清理未匹配法律特征的模板

删除条件：
1. transaction_nature 为空
2. contract_object 为空
3. metadata_info 中没有 knowledge_graph_match
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from app.models.contract_template import ContractTemplate

def clean_unmatched_templates():
    """清理未匹配法律特征的模板"""
    db = SessionLocal()

    try:
        # 查询所有模板
        all_templates = db.query(ContractTemplate).all()

        print(f"数据库中共有 {len(all_templates)} 个模板")

        # 找出未匹配的模板
        unmatched = []
        matched = []

        for template in all_templates:
            is_matched = True
            reasons = []

            # 检查 transaction_nature
            if not template.transaction_nature:
                is_matched = False
                reasons.append("transaction_nature 为空")

            # 检查 contract_object
            if not template.contract_object:
                is_matched = False
                reasons.append("contract_object 为空")

            # 检查 metadata_info 中的 knowledge_graph_match
            if not template.metadata_info:
                is_matched = False
                reasons.append("metadata_info 为空")
            elif not template.metadata_info.get("knowledge_graph_match"):
                is_matched = False
                reasons.append("knowledge_graph_match 为空")

            if is_matched:
                matched.append(template)
            else:
                unmatched.append((template, reasons))

        print(f"\n已匹配法律特征的模板: {len(matched)} 个")
        print(f"未匹配法律特征的模板: {len(unmatched)} 个")

        # 显示已匹配的模板
        if matched:
            print("\n=== 已匹配法律特征的模板 ===")
            for t in matched:
                kg_info = t.metadata_info.get("knowledge_graph_match", {}) if t.metadata_info else {}
                print(f"  [{t.id[:8]}] {t.name}")
                print(f"    分类: {t.category} / {t.subcategory or '无'}")
                print(f"    交易性质: {t.transaction_nature}")
                print(f"    合同标的: {t.contract_object}")
                print(f"    知识图谱匹配: {kg_info.get('matched_category', '无')}")
                print()

        # 显示未匹配的模板
        if unmatched:
            print("\n=== 未匹配法律特征的模板（将被删除）===")
            for t, reasons in unmatched:
                print(f"  [{t.id[:8]}] {t.name}")
                print(f"    原因: {', '.join(reasons)}")

        # 确认删除
        if unmatched:
            confirm = input(f"\n确认删除 {len(unmatched)} 个未匹配的模板吗？(yes/no): ")

            if confirm.lower() in ['yes', 'y']:
                for t, _ in unmatched:
                    db.delete(t)

                db.commit()
                print(f"\n[OK] 已删除 {len(unmatched)} 个未匹配的模板")

                # 重新统计
                remaining = db.query(ContractTemplate).count()
                print(f"[INFO] 数据库中剩余 {remaining} 个模板")
            else:
                print("[INFO] 取消删除操作")
        else:
            print("\n[INFO] 没有需要删除的模板")

    except Exception as e:
        db.rollback()
        print(f"[ERROR] 清理失败: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    clean_unmatched_templates()
