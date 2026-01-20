"""
合同分类与V2特征一致性检查工具

功能：
1. 检查分类字段的一致性（category vs primary_contract_type）
2. 检查V2特征值的有效性
3. 生成详细的检查报告
4. 批量修正分类不一致的问题

使用方式：
    python backend/scripts/check_category_consistency.py
"""
import os
import sys
import json
from typing import Dict, List, Tuple
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate


# V2特征的有效值列表
VALID_V2_VALUES = {
    "transaction_nature": [
        "asset_transfer", "service_delivery", "authorization",
        "entity_creation", "capital_finance", "resource_sharing",
        "dispute_resolution"
    ],
    "contract_object": [
        "tangible_goods", "human_labor", "ip", "equity",
        "monetary_debt", "data_traffic", "credibility"
    ],
    "complexity": [
        "internal_simple", "standard_commercial", "complex_strategic"
    ],
    "stance": [
        "buyer_friendly", "seller_friendly", "neutral"
    ]
}

# 中英文映射（用于兼容旧数据）
V2_VALUE_MAPPING = {
    "transaction_nature": {
        "转移所有权": "asset_transfer",
        "提供服务": "service_delivery",
        "许可使用": "authorization",
        "合作经营": "entity_creation",
        "融资借贷": "capital_finance",
        "劳动用工": "service_delivery",
        "争议解决": "dispute_resolution"
    },
    "contract_object": {
        "货物": "tangible_goods",
        "工程": "tangible_goods",
        "服务": "human_labor",
        "股权": "equity",
        "资金": "monetary_debt"
    },
    "complexity": {
        "简单": "internal_simple",
        "中等": "standard_commercial",
        "复杂": "complex_strategic"
    },
    "stance": {
        "中立": "neutral",
        "甲方": "buyer_friendly",
        "乙方": "seller_friendly",
        "平衡": "neutral"
    }
}


class CategoryConsistencyChecker:
    """分类一致性检查器"""

    def __init__(self, db: Session):
        self.db = db
        self.issues = []

    def check_all(self) -> Dict:
        """检查所有模板"""
        print("\n" + "="*80)
        print("合同分类与V2特征一致性检查")
        print("="*80 + "\n")

        templates = self.db.query(ContractTemplate).filter(
            ContractTemplate.status == 'active'
        ).all()

        print(f"找到 {len(templates)} 个活跃模板\n")

        stats = {
            "total": len(templates),
            "category_mismatch": 0,
            "invalid_v2_values": 0,
            "missing_v2": 0,
            "can_auto_fix": 0
        }

        for i, template in enumerate(templates, 1):
            print(f"[{i}/{len(templates)}] 检查: {template.name}")

            # 检查1: category vs primary_contract_type
            if template.category != template.primary_contract_type:
                print(f"  ⚠️  分类不一致:")
                print(f"     category: {template.category}")
                print(f"     primary_contract_type: {template.primary_contract_type}")

                self.issues.append({
                    "template_id": template.id,
                    "template_name": template.name,
                    "issue_type": "category_mismatch",
                    "category": template.category,
                    "primary_contract_type": template.primary_contract_type
                })
                stats["category_mismatch"] += 1
            else:
                print(f"  ✅ 分类一致")

            # 检查2: V2特征有效性
            v2_fields = {
                "transaction_nature": template.transaction_nature,
                "contract_object": template.contract_object,
                "complexity": template.complexity,
                "stance": template.stance
            }

            missing = [k for k, v in v2_fields.items() if not v]
            if missing:
                print(f"  ❌ 缺失V2字段: {', '.join(missing)}")
                stats["missing_v2"] += 1
            else:
                # 检查值是否有效
                invalid = []
                normalized = {}

                for field, value in v2_fields.items():
                    # 检查是否需要转换中文到英文
                    if value in V2_VALUE_MAPPING.get(field, {}):
                        normalized[field] = V2_VALUE_MAPPING[field][value]
                        print(f"  ℹ️  {field}: '{value}' -> '{normalized[field]}' (需要标准化)")
                    elif value not in VALID_V2_VALUES.get(field, []):
                        invalid.append({field: value})
                    else:
                        normalized[field] = value

                if invalid:
                    print(f"  ⚠️  无效的V2值: {invalid}")
                    stats["invalid_v2_values"] += 1
                    self.issues.append({
                        "template_id": template.id,
                        "template_name": template.name,
                        "issue_type": "invalid_v2",
                        "invalid_fields": invalid
                    })
                elif normalized != v2_fields:
                    # 需要标准化
                    print(f"  ℹ️  需要标准化V2值")
                    stats["can_auto_fix"] += 1
                    self.issues.append({
                        "template_id": template.id,
                        "template_name": template.name,
                        "issue_type": "needs_normalization",
                        "current": v2_fields,
                        "normalized": normalized
                    })
                else:
                    print(f"  ✅ V2特征有效")

        self.print_summary(stats)
        return stats

    def fix_category_mismatch(self):
        """修复分类不一致问题"""
        print("\n" + "="*80)
        print("修复分类不一致问题")
        print("="*80 + "\n")

        count = 0
        for issue in self.issues:
            if issue["issue_type"] == "category_mismatch":
                template = self.db.query(ContractTemplate).filter(
                    ContractTemplate.id == issue["template_id"]
                ).first()

                if template:
                    print(f"修复: {template.name}")
                    print(f"  将 primary_contract_type 从 '{template.primary_contract_type}'")
                    print(f"  改为 '{template.category}'")

                    template.primary_contract_type = template.category
                    count += 1

        if count > 0:
            self.db.commit()
            print(f"\n✅ 已修复 {count} 个模板的分类不一致问题")
        else:
            print("\n✅ 没有需要修复的分类不一致问题")

    def normalize_v2_values(self):
        """标准化V2特征值（中文转英文）"""
        print("\n" + "="*80)
        print("标准化V2特征值")
        print("="*80 + "\n")

        count = 0
        for issue in self.issues:
            if issue["issue_type"] == "needs_normalization":
                template = self.db.query(ContractTemplate).filter(
                    ContractTemplate.id == issue["template_id"]
                ).first()

                if template:
                    print(f"标准化: {template.name}")
                    normalized = issue["normalized"]

                    for field, value in normalized.items():
                        if getattr(template, field) != value:
                            print(f"  {field}: '{getattr(template, field)}' -> '{value}'")
                            setattr(template, field, value)

                    count += 1

        if count > 0:
            self.db.commit()
            print(f"\n✅ 已标准化 {count} 个模板的V2特征值")
        else:
            print("\n✅ 没有需要标准化的V2特征值")

    def print_summary(self, stats: Dict):
        """打印检查摘要"""
        print("\n" + "="*80)
        print("检查摘要")
        print("="*80)
        print(f"\n📊 总计: {stats['total']} 个模板")
        print(f"⚠️  分类不一致: {stats['category_mismatch']} 个")
        print(f"⚠️  无效V2值: {stats['invalid_v2_values']} 个")
        print(f"❌ 缺失V2特征: {stats['missing_v2']} 个")
        print(f"🔧 可自动修复: {stats['can_auto_fix']} 个")
        print("\n" + "="*80)

    def export_report(self, filename: str = None):
        """导出检查报告"""
        if not filename:
            filename = f"category_consistency_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = {
            "generated_at": datetime.now().isoformat(),
            "issues": self.issues,
            "summary": {
                "total_issues": len(self.issues),
                "by_type": {}
            }
        }

        # 统计问题类型
        for issue in self.issues:
            issue_type = issue["issue_type"]
            if issue_type not in report["summary"]["by_type"]:
                report["summary"]["by_type"][issue_type] = 0
            report["summary"]["by_type"][issue_type] += 1

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n📄 报告已导出: {filename}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description='合同分类与V2特征一致性检查')
    parser.add_argument('--fix-category', action='store_true', help='修复分类不一致问题')
    parser.add_argument('--normalize-v2', action='store_true', help='标准化V2特征值')
    parser.add_argument('--export', action='store_true', help='导出检查报告')
    parser.add_argument('--report-file', type=str, help='报告文件名')

    args = parser.parse_args()

    db = SessionLocal()
    checker = CategoryConsistencyChecker(db)

    try:
        # 执行检查
        stats = checker.check_all()

        # 修复分类不一致
        if args.fix_category:
            checker.fix_category_mismatch()

        # 标准化V2值
        if args.normalize_v2:
            checker.normalize_v2_values()

        # 导出报告
        if args.export:
            checker.export_report(args.report_file)

    finally:
        db.close()


if __name__ == "__main__":
    main()
