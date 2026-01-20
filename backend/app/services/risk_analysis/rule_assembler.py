# backend/app/services/risk_analysis/rule_assembler.py
"""
风险评估规则组装器 (增强版)

具备场景感知能力：
1. 根据合同状态 (Status) 动态调整审查侧重点
2. 根据交易综述 (Narrative) 自动召回特定领域规则
3. 根据主体角色 (Role) 注入合规检查规则
"""

import logging
import json
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.risk_analysis import RiskRulePackage

logger = logging.getLogger(__name__)


class RiskRuleAssembler:
    """
    智能风险评估规则组装器
    """

    def __init__(self, db: Session):
        self.db = db

    def assemble_rules(
        self,
        package_id: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        组装风险评估规则

        Args:
            package_id: 规则包 ID（如 "equity_penetration_v1"）
            context: 上下文信息，必须包含 'cross_doc_info' (来自增强分析)

        Returns:
            组装后的规则列表
        """
        logger.info(f"[RiskRuleAssembler] 开始组装规则包: {package_id}")

        # 1. 加载基础规则包 (Base Layer)
        package = self.db.query(RiskRulePackage).filter(
            RiskRulePackage.package_id == package_id,
            RiskRulePackage.is_active == True
        ).first()

        if not package:
            # 容错：如果找不到包，使用空列表，依赖动态规则
            logger.warning(f"[RiskRuleAssembler] 规则包 {package_id} 不存在，将仅使用动态规则")
            base_rules = []
        else:
            base_rules = [r for r in package.rules] if package.rules else []
            logger.info(f"[RiskRuleAssembler] 加载基础规则 {len(base_rules)} 条")

        # 2. 生成场景感知规则 (Contextual Layer)
        contextual_rules = self._get_smart_contextual_rules(context)
        if contextual_rules:
            logger.info(f"[RiskRuleAssembler] 注入场景规则 {len(contextual_rules)} 条")

        # 3. 合并与去重
        # 策略：动态规则优先级通常高于基础规则，放在前面或调整 priority
        final_rules = contextual_rules + base_rules

        # 4. 按优先级排序 (降序)
        final_rules.sort(key=lambda x: x.get("priority", 5), reverse=True)

        logger.info(f"[RiskRuleAssembler] 规则组装完成，共 {len(final_rules)} 条规则")
        return final_rules

    def _get_smart_contextual_rules(self, context: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        基于增强分析结果生成动态规则
        """
        if not context:
            return []

        rules = []
        
        # 提取上下文数据 (兼容 workflow 传入的结构)
        # cross_doc_info 包含了 enhanced_document_analysis 的输出
        cross_doc = context.get("cross_doc_info", {})
        classification = context.get("classification", {})
        
        # 获取增强分析的高维特征
        status = cross_doc.get("contract_status", "未知")
        summary = cross_doc.get("transaction_summary", "") or cross_doc.get("narrative_summary", "")
        parties = cross_doc.get("parties", []) # 可能是列表或字典，需做容错处理
        
        # === 维度 1: 基于合同状态的规则 ===
        status_rules = self._infer_rules_from_status(status)
        rules.extend(status_rules)

        # === 维度 2: 基于交易内容的领域规则 ===
        domain_rules = self._infer_rules_from_narrative(summary)
        rules.extend(domain_rules)

        # === 维度 3: 基于主体角色的规则 ===
        role_rules = self._infer_rules_from_parties(parties)
        rules.extend(role_rules)

        # === 维度 4: 基于文档类型的规则 (原有逻辑保留并增强) ===
        doc_type_rules = self._infer_rules_from_docs(classification)
        rules.extend(doc_type_rules)

        return rules

    def _infer_rules_from_status(self, status: str) -> List[Dict[str, Any]]:
        """根据合同状态调整审查重心"""
        rules = []
        
        if "磋商" in status or "意向" in status:
            rules.append({
                "rule_id": "ST_DRAFT_01",
                "rule_name": "缔约过失风险审查",
                "rule_prompt": "当前处于磋商阶段，重点审查：1) 是否存在单方承诺及其法律效力；2) 商业秘密保护条款是否完善；3) 意向金/定金的退还条件是否清晰。",
                "priority": 9,
                "risk_type": "contract_formation"
            })
        
        elif "争议" in status or "诉讼" in status or "违约" in status:
            rules.append({
                "rule_id": "ST_DISPUTE_01",
                "rule_name": "争议解决条款深度审查",
                "rule_prompt": "检测到存在争议倾向，请极度严格审查：1) 管辖法院/仲裁机构是否对我方有利；2) 违约金计算标准是否过高或过低；3) 证据保留条款（如送达地址确认书）。",
                "priority": 10,  # 最高优先级
                "risk_type": "litigation_risk"
            })
            
        elif "终止" in status or "解除" in status:
            rules.append({
                "rule_id": "ST_TERM_01",
                "rule_name": "合同解除后果审查",
                "rule_prompt": "审查合同解除后的清理义务：1) 存货/设备处理；2) 已付款项的结算与退回；3) 解除后的保密与竞业限制义务。",
                "priority": 9,
                "risk_type": "termination_risk"
            })

        return rules

    def _infer_rules_from_narrative(self, summary: str) -> List[Dict[str, Any]]:
        """根据交易综述关键词召回领域规则"""
        rules = []
        summary_lower = summary.lower()

        # 股权/投资类
        if any(k in summary_lower for k in ["股权", "股份", "增资", "投资", "股东"]):
            rules.append({
                "rule_id": "DOM_EQUITY_01",
                "rule_name": "公司法合规审查",
                "rule_prompt": "交易涉及股权变动，必须审查：1) 是否符合公司章程规定的优先购买权程序；2) 股东会决议的表决比例是否合法；3) 注册资本实缴情况及出资违约责任。",
                "priority": 8,
                "risk_type": "corporate_law"
            })

        # 借贷/担保类
        if any(k in summary_lower for k in ["借款", "贷款", "授信", "抵押", "质押"]):
            rules.append({
                "rule_id": "DOM_LOAN_01",
                "rule_name": "民间借贷/金融合规审查",
                "rule_prompt": "审查借贷关系合规性：1) 利率是否超过LPR的4倍（司法保护上限）；2) 是否存在'砍头息'或变相收费；3) 担保物权的登记有效性。",
                "priority": 9,
                "risk_type": "financial_compliance"
            })

        # 知识产权/软件开发
        if any(k in summary_lower for k in ["软件", "开发", "代码", "著作权", "ip", "license"]):
            rules.append({
                "rule_id": "DOM_IP_01",
                "rule_name": "知识产权归属审查",
                "rule_prompt": "重点审查IP归属：1) 委托开发成果的归属是否明确约定（无约定归受托方）；2) 是否包含开源软件传染性风险；3) 侵权赔偿责任是否有上限。",
                "priority": 8,
                "risk_type": "ip_risk"
            })

        return rules

    def _infer_rules_from_parties(self, parties: Any) -> List[Dict[str, Any]]:
        """根据主体角色注入规则"""
        rules = []
        
        # 兼容 parties 可能是列表或字典列表的情况
        party_roles = set()
        if isinstance(parties, list):
            for p in parties:
                if isinstance(p, dict):
                    role = p.get("role", "").lower()
                    party_roles.add(role)
                elif isinstance(p, str): # 容错
                    party_roles.add(p.lower())

        # 担保方风险
        if any("担保" in r or "guarantor" in r for r in party_roles):
            rules.append({
                "rule_id": "ROLE_GUARANTEE_01",
                "rule_name": "担保责任审查",
                "rule_prompt": "检测到担保方，审查：1) 担保方式（一般保证 vs 连带责任）；2) 担保期间是否明确（未约定则为主债务届满后6个月）；3) 担保范围是否包含违约金和实现债权的费用。",
                "priority": 8,
                "risk_type": "guarantee_law"
            })

        return rules

    def _infer_rules_from_docs(self, classification: Dict[str, List[str]]) -> List[Dict[str, Any]]:
        """基于文档类型的规则（保留原有逻辑）"""
        rules = []
        
        if classification.get("financial_report"):
            rules.append({
                "rule_id": "DOC_FIN_01",
                "rule_name": "财务真实性验证",
                "rule_prompt": "结合财报与合同金额，检查：1) 交易金额是否超出公司资产规模；2) 是否存在异常的关联交易资金流向。",
                "priority": 7,
                "risk_type": "financial_risk"
            })
            
        if classification.get("business_license"):
            rules.append({
                "rule_id": "DOC_LIC_01",
                "rule_name": "经营资质审查",
                "rule_prompt": "核对营业执照：1) 经营范围是否覆盖本次交易标的；2) 执照是否已过有效期。",
                "priority": 7,
                "risk_type": "compliance_risk"
            })
            
        return rules

    def format_rules_for_llm(self, rules: List[Dict[str, Any]]) -> str:
        """
        格式化为 Prompt (Markdown 格式)
        """
        if not rules:
            return "（无特定审查规则，请基于通用法律常识进行审查）"

        formatted = ["## 专项审查规则\n请严格应用以下规则对文档进行风险挖掘：\n"]

        for i, rule in enumerate(rules, 1):
            name = rule.get('rule_name', '未命名规则')
            prompt = rule.get('rule_prompt', '无描述')
            priority = rule.get('priority', 5)
            
            # 格式化为结构化块，方便 LLM 理解权重
            formatted.append(f"### [规则 {i}] {name}")
            formatted.append(f"- **优先级**: {priority}/10")
            formatted.append(f"- **执行指令**: {prompt}")
            formatted.append("")

        return "\n".join(formatted)

    # 辅助方法保持不变
    def get_package(self, package_id: str) -> Optional[RiskRulePackage]:
        return self.db.query(RiskRulePackage).filter(RiskRulePackage.package_id == package_id).first()

    def list_packages(self, category: Optional[str] = None) -> List[RiskRulePackage]:
        query = self.db.query(RiskRulePackage).filter(RiskRulePackage.is_active == True)
        if category:
            query = query.filter(RiskRulePackage.package_category == category)
        return query.order_by(RiskRulePackage.package_name).all()


def get_risk_rule_assembler(db: Optional[Session] = None) -> RiskRuleAssembler:
    if db is None:
        db = SessionLocal()
    return RiskRuleAssembler(db)