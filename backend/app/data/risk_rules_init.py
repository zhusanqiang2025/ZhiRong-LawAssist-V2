# backend/app/data/risk_rules_init.py
"""
风险评估规则初始化脚本

创建默认的风险评估规则，用于规则引擎扫描
"""

from app.database import SessionLocal
from app.models.risk_analysis import RiskAnalysisRule


def init_risk_rules():
    """初始化风险评估规则"""
    db = SessionLocal()
    try:
        # 股权穿透风险规则
        equity_rules = [
            RiskAnalysisRule(
                name="交叉持股风险",
                description="检测公司之间的交叉持股关系",
                scene_type="equity_penetration",
                rule_category="universal",
                risk_type="control_risk",
                content="检查文档中是否存在交叉持股的描述，识别可能的公司控制权风险",
                keywords=["交叉持股", "相互持股", "循环持股", "互为股东"],
                default_risk_level="high",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="代持股份风险",
                description="检测可能的股份代持情况",
                scene_type="equity_penetration",
                rule_category="universal",
                risk_type="ownership_risk",
                content="检查文档中是否存在股份代持、委托持股等安排，识别潜在的所有权风险",
                keywords=["代持", "委托持股", "名义股东", "实际控制人", "股权代持"],
                default_risk_level="high",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="关联交易风险",
                description="检测关联方交易披露情况",
                scene_type="equity_penetration",
                rule_category="universal",
                risk_type="transaction_risk",
                content="检查文档中是否充分披露关联方关系和交易情况",
                keywords=["关联交易", "关联方", "实际控制人", "控股股东"],
                default_risk_level="medium",
                is_system=True,
                is_active=True
            ),
        ]

        # 合同风险规则
        contract_rules = [
            RiskAnalysisRule(
                name="违约金过高风险",
                description="检测违约金是否超过合理范围",
                scene_type="contract_risk",
                rule_category="universal",
                risk_type="payment_risk",
                content="检查合同中的违约金条款是否超过合同总金额的30%或法律规定的合理范围",
                keywords=["违约金", "赔偿金", "损失赔偿"],
                pattern=r'违约金.*?(超过|超过.*?百分之|30%|50%|100%)',
                default_risk_level="medium",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="免责条款风险",
                description="检测单方面免责条款",
                scene_type="contract_risk",
                rule_category="universal",
                risk_type="liability_risk",
                content="检查合同中是否存在单方面免责或不承担责任的条款",
                keywords=["免责", "不承担责任", "概不负责", "免除责任"],
                default_risk_level="high",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="模糊条款风险",
                description="检测含义模糊的条款",
                scene_type="contract_risk",
                rule_category="universal",
                risk_type="ambiguity_risk",
                content="检查合同中是否存在含义模糊、可能导致争议的条款",
                keywords=["另行协商", "另行约定", "双方商定", "合理", "适当"],
                default_risk_level="medium",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="管辖条款风险",
                description="检测管辖法院和争议解决方式",
                scene_type="contract_risk",
                rule_category="universal",
                risk_type="jurisdiction_risk",
                content="检查合同中的管辖法院和争议解决方式是否合理",
                keywords=["管辖法院", "仲裁", "争议解决", "诉讼"],
                default_risk_level="low",
                is_system=True,
                is_active=True
            ),
        ]

        # 合规审查规则
        compliance_rules = [
            RiskAnalysisRule(
                name="反洗钱合规",
                description="检测反洗钱相关合规要求",
                scene_type="compliance_review",
                rule_category="universal",
                risk_type="aml_risk",
                content="检查文档是否符合反洗钱法律法规要求",
                keywords=["反洗钱", "客户身份识别", "大额交易", "可疑交易"],
                default_risk_level="high",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="数据保护合规",
                description="检测数据保护和隐私合规要求",
                scene_type="compliance_review",
                rule_category="universal",
                risk_type="privacy_risk",
                content="检查文档是否符合数据保护和隐私法律法规要求",
                keywords=["个人信息", "隐私", "数据保护", "敏感信息", "GDPR"],
                default_risk_level="high",
                is_system=True,
                is_active=True
            ),
        ]

        # 税务风险规则
        tax_rules = [
            RiskAnalysisRule(
                name="税务申报风险",
                description="检测税务申报相关风险",
                scene_type="tax_risk",
                rule_category="universal",
                risk_type="tax_filing_risk",
                content="检查文档中是否存在税务申报相关的风险点",
                keywords=["税务申报", "纳税", "税款", "税务机关"],
                default_risk_level="high",
                is_system=True,
                is_active=True
            ),
            RiskAnalysisRule(
                name="税务筹划风险",
                description="检测税务筹划合规性",
                scene_type="tax_risk",
                rule_category="universal",
                risk_type="tax_planning_risk",
                content="检查税务筹划方案是否合规，是否存在逃税风险",
                keywords=["税务筹划", "税收优惠", "避税", "逃税"],
                default_risk_level="medium",
                is_system=True,
                is_active=True
            ),
        ]

        # 合并所有规则
        all_rules = equity_rules + contract_rules + compliance_rules + tax_rules

        # 添加到数据库（避免重复）
        added_count = 0
        for rule in all_rules:
            existing = db.query(RiskAnalysisRule).filter(
                RiskAnalysisRule.name == rule.name,
                RiskAnalysisRule.scene_type == rule.scene_type
            ).first()
            if not existing:
                db.add(rule)
                added_count += 1

        db.commit()
        print(f"✓ 成功初始化 {added_count} 条风险评估规则")

        # 打印规则统计
        total = db.query(RiskAnalysisRule).filter(RiskAnalysisRule.is_system == True).count()
        print(f"✓ 系统规则总数: {total} 条")

        return True

    except Exception as e:
        print(f"✗ 初始化风险评估规则失败: {str(e)}")
        db.rollback()
        return False

    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("风险评估规则初始化")
    print("=" * 50)
    init_risk_rules()
    print("=" * 50)
