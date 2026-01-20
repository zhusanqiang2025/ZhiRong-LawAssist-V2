"""
合同模板V2特征自动检查与修复工具

功能：
1. 检查所有模板的V2特征完整性
2. 重新提取缺失或不准确的V2特征
3. 验证分类与V2特征的一致性
4. 生成检查报告
5. 批量修复问题

使用方式：
    python backend/scripts/check_and_fix_templates.py --dry-run  # 只检查不修复
    python backend/scripts/check_and_fix_templates.py --fix       # 检查并修复
    python backend/scripts/check_and_fix_templates.py --template-id xxx  # 检查单个模板
"""
import os
import sys
import json
import argparse
from typing import Dict, List, Optional
from datetime import datetime

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.contract_template import ContractTemplate
from app.services.template_feature_extractor import get_template_feature_extractor
from app.core.config import settings


class TemplateChecker:
    """合同模板检查器"""

    def __init__(self, db: Session):
        self.db = db
        self.results = {
            "total": 0,
            "complete": 0,
            "incomplete": 0,
            "missing_v2": 0,
            "missing_file": 0,
            "issues": [],
            "fixed": []
        }

    def check_all_templates(self) -> Dict:
        """检查所有模板"""
        print("\n" + "="*80)
        print("开始检查所有合同模板...")
        print("="*80 + "\n")

        templates = self.db.query(ContractTemplate).filter(
            ContractTemplate.status == 'active'
        ).all()

        self.results["total"] = len(templates)

        for template in templates:
            self.check_template(template)

        self.print_summary()
        return self.results

    def check_template(self, template: ContractTemplate) -> Dict:
        """检查单个模板"""
        issues = []

        print(f"\n检查模板: {template.name}")
        print(f"  ID: {template.id}")
        print(f"  分类: {template.category}")

        # 1. 检查V2特征完整性
        v2_fields = {
            "transaction_nature": template.transaction_nature,
            "contract_object": template.contract_object,
            "complexity": template.complexity,
            "stance": template.stance
        }

        missing_v2 = [k for k, v in v2_fields.items() if not v]

        if missing_v2:
            print(f"  ❌ 缺失V2特征: {', '.join(missing_v2)}")
            issues.append({
                "type": "missing_v2",
                "fields": missing_v2,
                "template_id": template.id
            })
            self.results["missing_v2"] += 1
        else:
            print(f"  ✅ V2特征完整")
            self.results["complete"] += 1

        # 2. 检查文件是否存在
        if template.file_url and os.path.exists(template.file_url):
            print(f"  ✅ 文件存在: {template.file_url}")
        else:
            print(f"  ❌ 文件缺失: {template.file_url}")
            issues.append({
                "type": "missing_file",
                "template_id": template.id,
                "file_url": template.file_url
            })
            self.results["missing_file"] += 1

        # 3. 检查V2特征值是否有效
        if not missing_v2:
            valid, invalid = self.validate_v2_features(v2_fields)
            if invalid:
                print(f"  ⚠️  无效的V2特征值: {invalid}")
                issues.append({
                    "type": "invalid_v2",
                    "invalid_fields": invalid,
                    "template_id": template.id
                })

        # 4. 检查分类一致性
        if template.category and template.primary_contract_type:
            if template.category != template.primary_contract_type:
                print(f"  ⚠️  分类不一致:")
                print(f"     category: {template.category}")
                print(f"     primary_contract_type: {template.primary_contract_type}")
                issues.append({
                    "type": "category_mismatch",
                    "template_id": template.id
                })

        if issues:
            self.results["incomplete"] += 1
            self.results["issues"].append({
                "template_id": template.id,
                "template_name": template.name,
                "issues": issues
            })

        return {
            "template": template,
            "issues": issues
        }

    def validate_v2_features(self, v2_fields: Dict) -> tuple:
        """验证V2特征值是否在有效范围内"""
        valid_fields = {
            "transaction_nature": [
                "asset_transfer", "service_delivery", "authorization",
                "entity_creation", "capital_finance", "resource_sharing",
                "dispute_resolution", "转移所有权", "提供服务", "许可使用",
                "合作经营", "融资借贷", "劳动用工", "争议解决"
            ],
            "contract_object": [
                "tangible_goods", "human_labor", "ip", "equity",
                "monetary_debt", "data_traffic", "credibility",
                "货物", "工程", "ip", "服务", "股权", "资金",
                "human_labor", "real_estate"
            ],
            "complexity": [
                "internal_simple", "standard_commercial", "complex_strategic",
                "simple", "中等", "复杂"
            ],
            "stance": [
                "buyer_friendly", "seller_friendly", "neutral",
                "party_a", "party_b", "balanced", "中立", "甲方", "乙方", "平衡"
            ]
        }

        valid = []
        invalid = []

        for field, value in v2_fields.items():
            if value in valid_fields.get(field, []):
                valid.append(field)
            else:
                invalid.append({field: value})

        return valid, invalid

    def fix_template(self, template: ContractTemplate, auto_fix: bool = False) -> bool:
        """修复单个模板的V2特征"""
        print(f"\n{'='*60}")
        print(f"修复模板: {template.name}")
        print(f"{'='*60}")

        # 检查文件是否存在
        if not template.file_url or not os.path.exists(template.file_url):
            print(f"❌ 文件不存在，无法自动修复: {template.file_url}")
            return False

        try:
            # 使用自动提取器重新提取V2特征
            print("📊 开始自动提取V2特征...")
            extractor = get_template_feature_extractor()
            extracted_features, note = extractor.extract_from_file(
                file_path=template.file_url,
                category_hint=template.category
            )

            print(f"✅ 提取完成:")
            print(f"   transaction_nature: {extracted_features.get('transaction_nature')}")
            print(f"   contract_object: {extracted_features.get('contract_object')}")
            print(f"   complexity: {extracted_features.get('complexity')}")
            print(f"   stance: {extracted_features.get('stance')}")
            print(f"   说明: {note}")

            if auto_fix:
                # 更新数据库
                template.transaction_nature = extracted_features.get('transaction_nature')
                template.contract_object = extracted_features.get('contract_object')
                template.complexity = extracted_features.get('complexity')
                template.stance = extracted_features.get('stance')

                # 更新metadata
                if not template.metadata_info:
                    template.metadata_info = {}
                template.metadata_info.update({
                    "auto_fixed": True,
                    "fixed_at": datetime.now().isoformat(),
                    "fix_note": note
                })

                self.db.commit()
                print(f"✅ 已保存到数据库")

                self.results["fixed"].append({
                    "template_id": template.id,
                    "template_name": template.name
                })
                return True
            else:
                print(f"\n💡 这是预览模式，使用 --fix 参数来实际应用修复")
                return False

        except Exception as e:
            print(f"❌ 修复失败: {str(e)}")
            return False

    def fix_all_templates(self, only_missing: bool = True):
        """批量修复所有模板"""
        print("\n" + "="*80)
        print("开始批量修复模板...")
        print("="*80 + "\n")

        query = self.db.query(ContractTemplate).filter(
            ContractTemplate.status == 'active'
        )

        if only_missing:
            # 只修复V2特征缺失的模板
            query = query.filter(
                (ContractTemplate.transaction_nature == None) |
                (ContractTemplate.contract_object == None) |
                (ContractTemplate.complexity == None) |
                (ContractTemplate.stance == None)
            )

        templates = query.all()
        print(f"找到 {len(templates)} 个需要修复的模板\n")

        fixed_count = 0
        for i, template in enumerate(templates, 1):
            print(f"\n[{i}/{len(templates)}]", end=" ")
            if self.fix_template(template, auto_fix=True):
                fixed_count += 1

        print(f"\n\n✅ 修复完成: {fixed_count}/{len(templates)} 个模板已修复")

    def print_summary(self):
        """打印检查摘要"""
        print("\n" + "="*80)
        print("检查摘要")
        print("="*80)

        results = self.results
        print(f"\n📊 总计: {results['total']} 个模板")
        print(f"✅ 完整: {results['complete']} 个")
        print(f"❌ 不完整: {results['incomplete']} 个")
        print(f"   - 缺失V2特征: {results['missing_v2']} 个")
        print(f"   - 文件缺失: {results['missing_file']} 个")
        print(f"🔧 已修复: {len(results['fixed'])} 个")

        if results['issues']:
            print(f"\n📋 问题列表:")
            for issue in results['issues'][:10]:  # 只显示前10个
                print(f"\n  模板: {issue['template_name']} (ID: {issue['template_id']})")
                for item in issue['issues']:
                    if item['type'] == 'missing_v2':
                        print(f"    ❌ 缺失V2字段: {', '.join(item['fields'])}")
                    elif item['type'] == 'missing_file':
                        print(f"    ❌ 文件缺失: {item['file_url']}")
                    elif item['type'] == 'invalid_v2':
                        print(f"    ⚠️  无效值: {item['invalid_fields']}")

            if len(results['issues']) > 10:
                print(f"\n  ... 还有 {len(results['issues']) - 10} 个问题未显示")

        print("\n" + "="*80)

    def export_report(self, filename: str = None):
        """导出检查报告"""
        if not filename:
            filename = f"template_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": {
                "total": self.results["total"],
                "complete": self.results["complete"],
                "incomplete": self.results["incomplete"],
                "missing_v2": self.results["missing_v2"],
                "missing_file": self.results["missing_file"],
                "fixed_count": len(self.results["fixed"])
            },
            "issues": self.results["issues"],
            "fixed": self.results["fixed"]
        }

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"\n📄 报告已导出: {filename}")


def main():
    parser = argparse.ArgumentParser(description='合同模板V2特征检查与修复工具')
    parser.add_argument('--dry-run', action='store_true', help='只检查不修复')
    parser.add_argument('--fix', action='store_true', help='检查并修复')
    parser.add_argument('--fix-all', action='store_true', help='修复所有模板（包括已有V2特征的）')
    parser.add_argument('--template-id', type=str, help='检查单个模板')
    parser.add_argument('--export', action='store_true', help='导出检查报告')
    parser.add_argument('--report-file', type=str, help='报告文件名')

    args = parser.parse_args()

    db = SessionLocal()
    checker = TemplateChecker(db)

    try:
        if args.template_id:
            # 检查单个模板
            template = db.query(ContractTemplate).filter(
                ContractTemplate.id == args.template_id
            ).first()

            if not template:
                print(f"❌ 未找到模板: {args.template_id}")
                return

            result = checker.check_template(template)

            if args.fix and result['issues']:
                checker.fix_template(template, auto_fix=True)

        else:
            # 检查所有模板
            checker.check_all_templates()

            # 修复模式
            if args.fix:
                checker.fix_all_templates(only_missing=not args.fix_all)

            # 导出报告
            if args.export:
                checker.export_report(args.report_file)

    finally:
        db.close()


if __name__ == "__main__":
    main()
