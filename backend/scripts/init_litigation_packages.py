"""
初始化案件分析模块数据

创建预设的案件类型包
"""

from sqlalchemy.orm import Session
from datetime import datetime

from app.database import SessionLocal
from app.models.litigation_analysis import LitigationCasePackage


def init_litigation_case_packages(db: Session):
    """
    初始化案件类型包
    """
    packages = [
        {
            "package_id": "contract_performance_v1",
            "package_name": "合同履约分析规则包",
            "package_category": "contract_dispute",
            "case_type": "contract_performance",
            "description": "用于分析合同履约情况，识别违约风险，制定诉讼方案",
            "applicable_positions": ["plaintiff", "defendant"],
            "target_documents": ["contract", "agreement", "supplementary_agreement"],
            "rules": [
                {
                    "rule_id": "CP001",
                    "rule_name": "合同主体资格审查",
                    "rule_prompt": "审查合同当事人的主体资格、民事行为能力、代理权限等",
                    "priority": 10
                },
                {
                    "rule_id": "CP002",
                    "rule_name": "合同条款效力分析",
                    "rule_prompt": "分析合同条款的效力，识别无效、可撤销、效力待定条款",
                    "priority": 9
                },
                {
                    "rule_id": "CP003",
                    "rule_name": "违约行为识别",
                    "rule_prompt": "识别违约行为的具体表现、违约程度、因果关系",
                    "priority": 10
                },
                {
                    "rule_id": "CP004",
                    "rule_name": "损失计算分析",
                    "rule_prompt": "分析违约造成的损失，包括直接损失和间接损失",
                    "priority": 8
                },
                {
                    "rule_id": "CP005",
                    "rule_name": "诉讼时效分析",
                    "rule_prompt": "分析诉讼时效，识别时效中断、中止、延长情形",
                    "priority": 9
                }
            ],
            "is_active": True,
            "is_system": True,
            "version": "1.0"
        },
        {
            "package_id": "complaint_defense_v1",
            "package_name": "起诉状分析规则包",
            "package_category": "litigation",
            "case_type": "complaint_defense",
            "description": "用于分析起诉状及相关证据，制定应诉策略和答辩方案",
            "applicable_positions": ["defendant"],
            "target_documents": ["complaint", "evidence", "court_document"],
            "rules": [
                {
                    "rule_id": "CD001",
                    "rule_name": "管辖权异议分析",
                    "rule_prompt": "分析法院是否有管辖权，是否存在管辖权异议的情形",
                    "priority": 10
                },
                {
                    "rule_id": "CD002",
                    "rule_name": "原告资格审查",
                    "rule_prompt": "审查原告的主体资格、诉讼权利能力",
                    "priority": 9
                },
                {
                    "rule_id": "CD003",
                    "rule_name": "诉讼请求合法性分析",
                    "rule_prompt": "分析诉讼请求是否明确、具体、合法",
                    "priority": 10
                },
                {
                    "rule_id": "CD004",
                    "rule_name": "证据充分性评估",
                    "rule_prompt": "评估原告所提交证据的充分性、合法性、关联性",
                    "priority": 10
                },
                {
                    "rule_id": "CD005",
                    "rule_name": "抗辩要点识别",
                    "rule_prompt": "识别有效的抗辩要点，包括实体抗辩和程序抗辩",
                    "priority": 9
                }
            ],
            "is_active": True,
            "is_system": True,
            "version": "1.0"
        },
        {
            "package_id": "judgment_appeal_v1",
            "package_name": "判决分析规则包",
            "package_category": "litigation",
            "case_type": "judgment_appeal",
            "description": "用于分析判决书及庭审笔录，制定上诉策略和证据思路",
            "applicable_positions": ["appellant", "appellee"],
            "target_documents": ["judgment", "court_record", "evidence"],
            "rules": [
                {
                    "rule_id": "JA001",
                    "rule_name": "判决事实认定审查",
                    "rule_prompt": "审查判决事实认定是否清楚、证据是否充分",
                    "priority": 10
                },
                {
                    "rule_id": "JA002",
                    "rule_name": "法律适用准确性分析",
                    "rule_prompt": "分析判决法律适用是否准确、有无适用法律错误",
                    "priority": 10
                },
                {
                    "rule_id": "JA003",
                    "rule_name": "程序合法性审查",
                    "rule_prompt": "审查审判程序是否合法，是否存在程序违法情形",
                    "priority": 9
                },
                {
                    "rule_id": "JA004",
                    "rule_name": "上诉理由识别",
                    "rule_prompt": "识别有效的上诉理由，包括事实认定错误、法律适用错误、程序违法",
                    "priority": 10
                },
                {
                    "rule_id": "JA005",
                    "rule_name": "二审胜诉概率评估",
                    "rule_prompt": "基于上诉理由和现有证据，评估二审胜诉概率",
                    "priority": 8
                }
            ],
            "is_active": True,
            "is_system": True,
            "version": "1.0"
        },
        {
            "package_id": "evidence_preservation_v1",
            "package_name": "保全申请规则包",
            "package_category": "procedural",
            "case_type": "evidence_preservation",
            "description": "用于财产保全和证据保全申请的策略制定",
            "applicable_positions": ["plaintiff", "applicant"],
            "target_documents": ["application", "evidence", "asset_proof"],
            "rules": [
                {
                    "rule_id": "EP001",
                    "rule_name": "保全必要性分析",
                    "rule_prompt": "分析保全的必要性，是否存在证据灭失或难以取得的情形",
                    "priority": 10
                },
                {
                    "rule_id": "EP002",
                    "rule_name": "担保金额确定",
                    "rule_prompt": "根据保全财产类型和金额，确定合理的担保金额",
                    "priority": 9
                },
                {
                    "rule_id": "EP003",
                    "rule_name": "财产线索分析",
                    "rule_prompt": "分析被申请人财产线索，识别可供保全的财产",
                    "priority": 8
                },
                {
                    "rule_id": "EP004",
                    "rule_name": "保全错误风险",
                    "rule_prompt": "分析申请保全可能存在的错误，识别潜在赔偿责任",
                    "priority": 9
                }
            ],
            "is_active": True,
            "is_system": True,
            "version": "1.0"
        },
        {
            "package_id": "enforcement_v1",
            "package_name": "强制执行规则包",
            "package_category": "procedural",
            "case_type": "enforcement",
            "description": "用于判决执行分析和财产线索查找",
            "applicable_positions": ["plaintiff", "applicant"],
            "target_documents": ["judgment", "court_order", "asset_info"],
            "rules": [
                {
                    "rule_id": "EF001",
                    "rule_name": "执行依据审查",
                    "rule_prompt": "审查执行依据的合法性和有效性",
                    "priority": 10
                },
                {
                    "rule_id": "EF002",
                    "rule_name": "被执行人财产调查",
                    "rule_prompt": "调查被执行人财产状况，识别可执行财产",
                    "priority": 9
                },
                {
                    "rule_id": "EF003",
                    "rule_name": "执行措施选择",
                    "rule_prompt": "根据被执行人财产状况，选择合适的执行措施",
                    "priority": 8
                },
                {
                    "rule_id": "EF004",
                    "rule_name": "执行异议应对",
                    "rule_prompt": "分析可能面临的执行异议，制定应对策略",
                    "priority": 7
                }
            ],
            "is_active": True,
            "is_system": True,
            "version": "1.0"
        },
        {
            "package_id": "arbitration_v1",
            "package_name": "仲裁程序规则包",
            "package_category": "procedural",
            "case_type": "arbitration",
            "description": "用于仲裁申请、答辩、证据策略制定",
            "applicable_positions": ["applicant", "respondent"],
            "target_documents": ["arbitration_application", "arbitration_agreement", "evidence"],
            "rules": [
                {
                    "rule_id": "AR001",
                    "rule_name": "仲裁协议效力分析",
                    "rule_prompt": "分析仲裁协议的效力，识别仲裁条款的有效性",
                    "priority": 10
                },
                {
                    "rule_id": "AR002",
                    "rule_name": "仲裁管辖权分析",
                    "rule_prompt": "分析仲裁委员会是否有管辖权",
                    "priority": 10
                },
                {
                    "rule_id": "AR003",
                    "rule_name": "仲裁请求合法性分析",
                    "rule_prompt": "分析仲裁请求是否明确、具体、合法",
                    "priority": 9
                },
                {
                    "rule_id": "AR004",
                    "rule_name": "仲裁证据规则分析",
                    "rule_prompt": "分析仲裁中的证据规则，制定证据策略",
                    "priority": 8
                },
                {
                    "rule_id": "AR005",
                    "rule_name": "仲裁裁决执行分析",
                    "rule_prompt": "分析仲裁裁决的执行可能性和策略",
                    "priority": 9
                }
            ],
            "is_active": True,
            "is_system": True,
            "version": "1.0"
        }
    ]

    for pkg_data in packages:
        # 检查是否已存在
        existing = db.query(LitigationCasePackage).filter(
            LitigationCasePackage.package_id == pkg_data["package_id"]
        ).first()

        if not existing:
            package = LitigationCasePackage(
                package_id=pkg_data["package_id"],
                package_name=pkg_data["package_name"],
                package_category=pkg_data["package_category"],
                case_type=pkg_data["case_type"],
                description=pkg_data["description"],
                applicable_positions=pkg_data["applicable_positions"],
                target_documents=pkg_data["target_documents"],
                rules=pkg_data["rules"],
                is_active=pkg_data["is_active"],
                is_system=pkg_data["is_system"],
                version=pkg_data["version"]
            )
            db.add(package)
            print(f"创建案件类型包: {package.package_name}")
        else:
            print(f"案件类型包已存在: {existing.package_name}")

    db.commit()


if __name__ == "__main__":
    db = SessionLocal()
    try:
        init_litigation_case_packages(db)
        print("案件分析模块数据初始化完成")
    finally:
        db.close()
