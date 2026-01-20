# backend/app/scripts/init_risk_rule_packages.py
"""
初始化风险评估规则包数据

运行方式：
python -m app.scripts.init_risk_rule_packages
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.risk_analysis import RiskRulePackage
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 预设规则包数据
PRESET_PACKAGES = [
    {
        "package_id": "equity_penetration_v1",
        "package_name": "股权穿透风险评估规则包",
        "package_category": "equity_risk",
        "description": "用于分析公司股权结构、识别控制权和关联交易风险",
        "applicable_scenarios": ["equity_penetration", "equity_structure", "shareholder_analysis"],
        "target_entities": ["company", "person"],
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "EP001",
                "rule_name": "交叉持股检测",
                "rule_prompt": "检查是否存在交叉持股或循环持股结构，分析其对控制权的影响。重点关注：1) A公司持有B公司股份，同时B公司也持有A公司股份；2) 通过多层嵌套形成的循环持股；3) 交叉持股对决策独立性的影响。",
                "priority": 10,
                "risk_type": "control_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "EP002",
                "rule_name": "实际控制人识别",
                "rule_prompt": "穿透多层股权结构，识别最终的实际控制人。分析要点：1) 追溯至自然人或国资主体；2) 识别一致行动人；3) 分析表决权委托协议；4) 评估实际控制人的控制力。",
                "priority": 9,
                "risk_type": "control_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "EP003",
                "rule_name": "关联交易风险",
                "rule_prompt": "识别可能存在的关联交易及其披露情况。检查内容：1) 关联方识别（股东控制的企业、董事监事高管控制的企业）；2) 关联交易的定价是否公允；3) 是否按规定披露；4) 是否存在利益输送嫌疑。",
                "priority": 8,
                "risk_type": "compliance_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "EP004",
                "rule_name": "股权集中度分析",
                "rule_prompt": "分析股权集中度对决策效率的影响。评估维度：1) 股权分散度（前五大股东持股比例）；2) 是否存在单一控股股东；3) 中小股东权益保护机制；4) 股东会决议通过难度。",
                "priority": 7,
                "risk_type": "governance_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "EP005",
                "rule_name": "股权质押风险",
                "rule_prompt": "检测股东股权质押情况，评估潜在风险。关注：1) 质押股份比例；2) 质权人情况；3) 质押期限；4) 平仓风险对控制权稳定性的影响。",
                "priority": 8,
                "risk_type": "financial_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "EP006",
                "rule_name": "外资准入限制",
                "rule_prompt": "检查是否存在外商投资准入限制。核实：1) 是否在《外商投资准入负面清单》范围内；2) 是否需要特殊行业许可；3) 外资比例限制；4) 安全审查要求。",
                "priority": 7,
                "risk_type": "compliance_risk",
                "default_risk_level": "high"
            }
        ]
    },
    {
        "package_id": "investment_project_v1",
        "package_name": "投资项目风险评估规则包",
        "package_category": "investment_risk",
        "description": "用于评估投资项目的各类风险",
        "applicable_scenarios": ["investment_project", "equity_investment", "m_a"],
        "target_entities": ["company", "project"],
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "IP001",
                "rule_name": "市场风险评估",
                "rule_prompt": "评估项目面临的市场竞争、需求变化等风险。分析：1) 市场规模和增长趋势；2) 竞争对手情况；3) 技术变革风险；4) 客户集中度风险。",
                "priority": 10,
                "risk_type": "market_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "IP002",
                "rule_name": "财务风险评估",
                "rule_prompt": "分析项目的财务结构、盈利能力、现金流风险。评估：1) 历史财务数据真实性；2) 收入预测合理性；3) 成本结构稳定性；4) 现金流充裕度；5) 偿债能力。",
                "priority": 10,
                "risk_type": "financial_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "IP003",
                "rule_name": "法律合规风险",
                "rule_prompt": "检查项目是否符合相关法律法规要求。核实：1) 行业许可资质；2) 环保合规；3) 土地使用权；4) 知识产权归属；5) 诉讼仲裁风险。",
                "priority": 9,
                "risk_type": "compliance_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "IP004",
                "rule_name": "运营风险评估",
                "rule_prompt": "评估项目运营过程中可能遇到的风险。关注：1) 核心团队稳定性；2) 技术依赖度；3) 供应链稳定性；4) 质量控制体系；5) 安全生产风险。",
                "priority": 8,
                "risk_type": "operational_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "IP005",
                "rule_name": "估值合理性分析",
                "rule_prompt": "评估项目估值的合理性。检查：1) 估值方法选择；2) 可比公司估值水平；3) 增长假设合理性；4) 敏感性分析；5) 退出方式可行性。",
                "priority": 9,
                "risk_type": "valuation_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "IP006",
                "rule_name": "投资结构风险",
                "rule_prompt": "分析投资结构的合理性。审查：1) 股权比例设置；2) 表决权安排；3) 退出机制；4) 优先清算权；5) 反稀释条款；6) 对赌条款（VAM）风险。",
                "priority": 8,
                "risk_type": "structural_risk",
                "default_risk_level": "medium"
            }
        ]
    },
    {
        "package_id": "corporate_intermingling_v1",
        "package_name": "公司混同风险评估规则包",
        "package_category": "governance_risk",
        "description": "用于识别公司人格混同风险，保护股东有限责任",
        "applicable_scenarios": ["corporate_intermingling", "piercing_veil", "compliance_review"],
        "target_entities": ["company", "person"],
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "CI001",
                "rule_name": "资产混同检测",
                "rule_prompt": "检查是否存在公司与股东资产混同的情况。排查：1) 银行账户混用；2) 固定资产登记混乱；3) 资金往来无明确记载；4) 财务记录不区分。",
                "priority": 10,
                "risk_type": "asset_risk",
                "default_risk_level": "critical"
            },
            {
                "rule_id": "CI002",
                "rule_name": "业务混同检测",
                "rule_prompt": "分析公司业务与股东个人/其他公司是否存在混同。识别：1) 交易主体不明确；2) 合同签署混乱；3) 发票开具与实际交易不符；4) 业务人员混用。",
                "priority": 10,
                "risk_type": "business_risk",
                "default_risk_level": "critical"
            },
            {
                "rule_id": "CI003",
                "rule_name": "财务混同检测",
                "rule_prompt": "检查财务账户、会计记录是否存在混同。审查：1) 会计账簿是否独立；2) 财务报表编制规范性；3) 税务申报独立性；4) 审计报告意见。",
                "priority": 9,
                "risk_type": "financial_risk",
                "default_risk_level": "critical"
            },
            {
                "rule_id": "CI004",
                "rule_name": "人员混同检测",
                "rule_prompt": "分析公司高管、员工是否存在交叉任职导致混同。关注：1) 法定代表人兼任；2) 财务人员共用；3) 办公场所混同；4) 通讯方式混用。",
                "priority": 8,
                "risk_type": "personnel_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "CI005",
                "rule_name": "治理结构混同",
                "rule_prompt": "评估公司治理结构是否独立。检查：1) 股东会、董事会独立性；2) 决策程序规范性；3) 关联公司控制关系；4) 内部控制有效性。",
                "priority": 7,
                "risk_type": "governance_risk",
                "default_risk_level": "high"
            }
        ]
    },
    {
        "package_id": "contract_risk_v1",
        "package_name": "合同条款风险评估规则包",
        "package_category": "contract_risk",
        "description": "用于评估合同条款的法律风险和商务风险",
        "applicable_scenarios": ["contract_review", "contract_signing", "contract_negotiation"],
        "target_entities": ["contract"],
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "CR001",
                "rule_name": "合同主体资格审查",
                "rule_prompt": "审查合同当事人的主体资格和履约能力。核实：1) 营业执照有效性；2) 特殊行业许可证；3) 注册资本与实缴资本；4) 涉诉失信情况；5) 授权代表签字权限。",
                "priority": 10,
                "risk_type": "counterparty_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "CR002",
                "rule_name": "合同效力风险",
                "rule_prompt": "评估合同是否存在效力瑕疵。检查：1) 是否违反法律强制性规定；2) 是否损害社会公共利益；3) 恶意串通损害第三人利益；4) 以合法形式掩盖非法目的；5) 格式条款效力。",
                "priority": 9,
                "risk_type": "validity_risk",
                "default_risk_level": "critical"
            },
            {
                "rule_id": "CR003",
                "rule_name": "付款条款风险",
                "rule_prompt": "审查付款条款的风险点。关注：1) 付款条件明确性；2) 付款时间节点；3) 违约金计算方式；4) 发票开具要求；5) 税务承担约定；6) 汇率风险（如适用）。",
                "priority": 8,
                "risk_type": "payment_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "CR004",
                "rule_name": "违约责任条款",
                "rule_prompt": "分析违约责任条款的完备性和公平性。评估：1) 违约行为定义是否清晰；2) 违约金比例是否合理；3) 免责条款；4) 不可抗力条款；5) 继续履行与解除合同的选择权。",
                "priority": 9,
                "risk_type": "liability_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "CR005",
                "rule_name": "保密与知识产权条款",
                "rule_prompt": "审查保密和知识产权保护条款。检查：1) 保密信息定义范围；2) 保密义务期限；3) 知识产权归属约定；4) 违约补救措施；5) 专利商标许可条款。",
                "priority": 7,
                "risk_type": "ip_risk",
                "default_risk_level": "medium"
            },
            {
                "rule_id": "CR006",
                "rule_name": "争议解决条款",
                "rule_prompt": "评估争议解决机制的合理性。分析：1) 管辖法院选择；2) 仲裁条款效力；3) 适用法律选择；4) 争议解决成本预估；5) 执行便利性。",
                "priority": 7,
                "risk_type": "dispute_risk",
                "default_risk_level": "low"
            }
        ]
    },
    {
        "package_id": "tax_risk_v1",
        "package_name": "税务风险评估规则包",
        "package_category": "tax_risk",
        "description": "用于评估企业税务合规风险和税务筹划风险",
        "applicable_scenarios": ["tax_review", "compliance_review", "due_diligence"],
        "target_entities": ["company"],
        "version": "1.0.0",
        "rules": [
            {
                "rule_id": "TR001",
                "rule_name": "税务登记合规性",
                "rule_prompt": "检查税务登记的合规性。核实：1) 税务登记证有效性；2) 一般纳税人资格；3) 税种核定完整性；4) 发票领购资格；5) 税控设备管理。",
                "priority": 9,
                "risk_type": "registration_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "TR002",
                "rule_name": "发票管理风险",
                "rule_prompt": "评估发票管理的合规风险。审查：1) 虚开发票风险；2) 发票品目与实际业务一致性；3) 发票存根保管；4) 进项税额抵扣合规性；5) 红字发票处理。",
                "priority": 10,
                "risk_type": "invoice_risk",
                "default_risk_level": "critical"
            },
            {
                "rule_id": "TR003",
                "rule_name": "税收优惠政策适用",
                "rule_prompt": "检查税收优惠政策适用的合规性。评估：1) 优惠资格获取合法性；2) 优惠条件持续满足；3) 备案资料完整性；4) 优惠政策变更影响；5) 存续期间合规性。",
                "priority": 8,
                "risk_type": "incentive_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "TR004",
                "rule_name": "关联交易税务风险",
                "rule_prompt": "分析关联交易的税务风险。关注：1) 转让定价文档准备；2) 关联方利息扣除；3) 关联劳务收费；4) 税务机关特别纳税调整风险；5) 成本分摊协议合规性。",
                "priority": 9,
                "risk_type": "transfer_pricing_risk",
                "default_risk_level": "high"
            },
            {
                "rule_id": "TR005",
                "rule_name": "跨境税务风险",
                "rule_prompt": "评估跨境业务的税务风险。检查：1) 非居民纳税人源泉扣缴；2) 常设机构认定；3) 税收协定适用；4) 对外支付备案；5) 受控外国企业管理。",
                "priority": 8,
                "risk_type": "cross_border_risk",
                "default_risk_level": "high"
            }
        ]
    }
]


def init_risk_rule_packages(db: Session):
    """初始化规则包数据"""

    logger.info("[InitRiskRulePackages] 开始初始化规则包数据...")

    created_count = 0
    updated_count = 0

    for package_data in PRESET_PACKAGES:
        # 检查是否已存在
        existing = db.query(RiskRulePackage).filter(
            RiskRulePackage.package_id == package_data["package_id"]
        ).first()

        if existing:
            logger.info(f"[InitRiskRulePackages] 更新规则包: {package_data['package_name']}")
            # 更新现有规则包
            for key, value in package_data.items():
                if key != "package_id":  # 不更新主键
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            updated_count += 1
        else:
            logger.info(f"[InitRiskRulePackages] 创建规则包: {package_data['package_name']}")
            # 创建新规则包
            new_package = RiskRulePackage(
                **package_data,
                is_active=True,
                is_system=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(new_package)
            created_count += 1

    try:
        db.commit()
        logger.info(f"[InitRiskRulePackages] 初始化完成: 创建 {created_count} 个，更新 {updated_count} 个")
    except Exception as e:
        db.rollback()
        logger.error(f"[InitRiskRulePackages] 初始化失败: {e}")
        raise


def main():
    """主函数"""
    db = SessionLocal()
    try:
        init_risk_rule_packages(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
