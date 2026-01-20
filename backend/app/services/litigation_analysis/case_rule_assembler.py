# backend/app/services/litigation_analysis/case_rule_assembler.py
"""
案件规则组装器 (Case Rule Assembler) - 智能增强版

核心升级：
1. 深度利用预整理数据：根据案情综述、争议焦点、金额等自动召回规则。
2. 动态权重：根据用户所处的诉讼阶段（场景）动态调整规则优先级。
3. 扩充规则库：增加了针对仲裁、执行、证据突袭等高频场景的实战规则。
"""

import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RuleCategory(str, Enum):
    """规则类别枚举"""
    CLAIM = "claim"           # 请求权基础 (进攻)
    DEFENSE = "defense"       # 抗辩事由 (防守)
    EVIDENCE = "evidence"     # 证据规则 (质证)
    PROCEDURE = "procedure"   # 程序规则 (管辖/时效/上诉)
    STRATEGY = "strategy"     # 诉讼策略
    RISK = "risk"             # 风险提示


@dataclass
class LitigationRule:
    """案件分析规则模型"""
    id: str
    case_type_keywords: List[str] # 适用案由关键词，如 ["借贷", "欠款"]
    scenario_scope: List[str]     # 适用场景，如 ["pre_litigation", "defense"]
    category: RuleCategory
    name: str
    legal_source: str
    prompt_template: str
    check_points: List[str]
    weight: float = 1.0
    is_active: bool = True


class CaseRuleAssembler:
    """案件规则组装器"""

    def __init__(self):
        # 实际项目中应注入 DB Session
        pass

    def assemble_rules(
        self,
        package_id: str,
        context: Dict[str, Any]
    ) -> List[str]:
        """
        组装规则的主入口
        
        Args:
            context: 必须包含 case_type, scenario, preorganized (含 enhanced_info)
        """
        case_type = context.get("case_type", "general")
        scenario = context.get("scenario", "pre_litigation")
        
        # 提取增强的案情信息 (这是我们 Phase 1 的成果)
        preorganized = context.get("preorganized", {})

        # 添加类型检查
        if not isinstance(preorganized, dict):
            logger.warning(f"[RuleAssembler] preorganized 不是字典类型: {type(preorganized)}")
            preorganized = {}

        enhanced_info = context.get("enhanced_info")
        if enhanced_info is None or not isinstance(enhanced_info, dict):
            enhanced_info = preorganized.get("enhanced_analysis_compatible", {}) if isinstance(preorganized, dict) else {}
        
        logger.info(f"[RuleAssembler] 开始组装规则: 案由={case_type}, 场景={scenario}")

        try:
            # 1. 获取规则全集 (模拟 DB)
            all_rules = self._get_mock_rules_db()

            # 2. 初步筛选：基于案由和场景
            candidate_rules = []
            for rule in all_rules:
                # 2.1 案由匹配 (模糊匹配)
                if rule.case_type_keywords:
                    if not any(kw in case_type for kw in rule.case_type_keywords) and "general" not in rule.case_type_keywords:
                        continue
                
                # 2.2 场景匹配
                if rule.scenario_scope and scenario not in rule.scenario_scope:
                    continue
                    
                candidate_rules.append(rule)

            # 3. 深度筛选与加权：基于案情细节 (Context Aware)
            active_rules = self._apply_context_intelligence(candidate_rules, enhanced_info, scenario)

            # 4. 格式化输出
            formatted_prompts = self._format_rules_to_prompts(active_rules)

            logger.info(f"[RuleAssembler] 组装完成，命中 {len(active_rules)} 条规则")
            return formatted_prompts

        except Exception as e:
            logger.error(f"[RuleAssembler] 规则组装失败: {e}", exc_info=True)
            return self._get_fallback_rules()

    def _apply_context_intelligence(
        self,
        rules: List[LitigationRule],
        enhanced_info: Any,  # 改为 Any 类型以支持容错
        scenario: str
    ) -> List[LitigationRule]:
        """
        利用预整理的案情信息，动态调整规则权重
        """
        # 添加类型检查
        if not isinstance(enhanced_info, dict):
            logger.warning(f"[RuleAssembler] enhanced_info 不是字典类型: {type(enhanced_info)}")
            enhanced_info = {}

        # 提取关键特征
        summary = (enhanced_info.get("transaction_summary") or "") + (enhanced_info.get("case_narrative") or "")
        dispute = enhanced_info.get("dispute_focus") or enhanced_info.get("core_dispute") or ""
        summary_lower = (summary + dispute).lower()
        
        adjusted_rules = []
        
        for rule in rules:
            final_weight = rule.weight
            
            # --- 智能加权逻辑 ---
            
            # 1. 涉及时效/期限
            if "时间" in summary_lower or "期限" in summary_lower or "过期" in summary_lower:
                if rule.category == RuleCategory.PROCEDURE:
                    final_weight += 2.0
            
            # 2. 涉及担保/抵押
            if "担保" in summary_lower or "抵押" in summary_lower:
                if "担保" in rule.name:
                    final_weight += 3.0
            
            # 3. 涉及公司/股权
            if "股权" in summary_lower or "股东" in summary_lower:
                if "公司法" in rule.legal_source:
                    final_weight += 2.0

            # 4. 证据薄弱 (通过关键词猜测)
            if "口头" in summary_lower or "缺失" in summary_lower:
                if rule.category == RuleCategory.EVIDENCE:
                    final_weight += 2.0

            # 5. 场景特化权重
            if scenario == "defense" and rule.category == RuleCategory.DEFENSE:
                final_weight += 1.5
            elif scenario == "pre_litigation" and rule.category == RuleCategory.CLAIM:
                final_weight += 1.5

            rule.weight = final_weight
            adjusted_rules.append(rule)

        # 按权重降序排序，取前 15 条 (避免 Token 溢出)
        adjusted_rules.sort(key=lambda x: x.weight, reverse=True)
        return adjusted_rules[:15]

    def _format_rules_to_prompts(self, rules: List[LitigationRule]) -> List[str]:
        """格式化为 Prompt"""
        prompts = []
        for idx, rule in enumerate(rules, 1):
            check_points_str = "、".join(rule.check_points)
            instruction = rule.prompt_template.replace("{check_points}", check_points_str)
            
            # 增加权重标签提示 LLM
            priority_tag = "【高优先级】" if rule.weight >= 3.0 else ""
            
            rule_text = (
                f"### 规则 {idx} {priority_tag}: {rule.name}\n"
                f"- **法律依据**: {rule.legal_source}\n"
                f"- **审查指令**: {instruction}"
            )
            prompts.append(rule_text)
        return prompts

    def _get_fallback_rules(self) -> List[str]:
        return [
            "### 通用规则: 事实与法律分析\n请基于中国现行法律，分析案件基本事实、法律关系及潜在风险。",
            "### 通用规则: 证据三性\n请审查现有证据的真实性、合法性和关联性。"
        ]

    def _get_mock_rules_db(self) -> List[LitigationRule]:
        """
        模拟规则数据库
        """
        db = []
        
        # ============ 1. 程序与管辖 (通用) ============
        db.append(LitigationRule(
            id="proc_01", case_type_keywords=["general"],
            scenario_scope=["pre_litigation", "defense"],
            category=RuleCategory.PROCEDURE,
            name="管辖权异议审查",
            legal_source="《民事诉讼法》第22条、35条",
            prompt_template="审查是否存在管辖权异议的空间。检查：{check_points}。如发现管辖约定不明或违反级别管辖，请提示提出管辖权异议。",
            check_points=["合同约定的管辖法院是否明确", "被告住所地是否变化", "是否违反专属管辖规定"],
            weight=2.0
        ))
        
        db.append(LitigationRule(
            id="proc_02", case_type_keywords=["general"],
            scenario_scope=["pre_litigation", "defense"],
            category=RuleCategory.PROCEDURE,
            name="诉讼时效审查",
            legal_source="《民法典》第188条",
            prompt_template="严格计算诉讼时效。检查：{check_points}。如果最后一次有效催收距离现在超过3年，提示时效抗辩风险。",
            check_points=["借款/违约发生日", "最后一次还款日", "书面催收记录", "诉讼中断事由"],
            weight=2.5
        ))

        # ============ 2. 民间借贷/金融 ============
        db.append(LitigationRule(
            id="loan_01", case_type_keywords=["借贷", "欠款", "金融"],
            scenario_scope=["pre_litigation", "defense", "appeal"],
            category=RuleCategory.CLAIM,
            name="借贷合意与交付审查",
            legal_source="《民法典》第679条",
            prompt_template="审查借贷关系的核心证据链：{check_points}。缺一不可，若仅有转账凭证而无借据，需警惕被抗辩为其他经济往来。",
            check_points=["借条/合同 (合意证明)", "银行流水/收据 (交付证明)"],
            weight=3.0
        ))

        db.append(LitigationRule(
            id="loan_02", case_type_keywords=["借贷", "金融"],
            scenario_scope=["pre_litigation", "defense"],
            category=RuleCategory.RISK,
            name="利率合规性审查",
            legal_source="《最高法民间借贷规定》",
            prompt_template="计算综合年化利率（含利息、服务费、担保费等）。{check_points}。超过部分不受法律保护，甚至可能导致已支付利息抵扣本金。",
            check_points=["2020.8.20前：24%/36%红线", "2020.8.20后：4倍LPR上限"],
            weight=2.0
        ))
        
        db.append(LitigationRule(
            id="loan_03", case_type_keywords=["借贷"],
            scenario_scope=["defense"],
            category=RuleCategory.DEFENSE,
            name="职业放贷人抗辩",
            legal_source="《九民纪要》第53条",
            prompt_template="分析原告特征。如果原告{check_points}，可主张其为职业放贷人，借款合同无效。",
            check_points=["短时间内提起大量民间借贷诉讼", "以放贷为业", "无放贷资质"],
            weight=2.5
        ))

        # ============ 3. 买卖合同/货款 ============
        db.append(LitigationRule(
            id="trade_01", case_type_keywords=["买卖", "货款", "采购"],
            scenario_scope=["pre_litigation", "defense"],
            category=RuleCategory.EVIDENCE,
            name="货物交付与质量审查",
            legal_source="《民法典》买卖合同章",
            prompt_template="审查货款支付条件的成就情况：{check_points}。仅有发票不足以证明交易真实发生。",
            check_points=["送货单/签收单 (交付证明)", "对账单 (结算证明)", "质量异议期内的通知记录"],
            weight=2.5
        ))

        # ============ 4. 公司/股权 ============
        db.append(LitigationRule(
            id="corp_01", case_type_keywords=["股权", "股东", "公司"],
            scenario_scope=["pre_litigation", "defense"],
            category=RuleCategory.CLAIM,
            name="股权转让效力审查",
            legal_source="《公司法》",
            prompt_template="审查股权转让的程序瑕疵：{check_points}。程序违规可能导致转让合同效力待定或可撤销。",
            check_points=["其他股东过半数同意", "优先购买权通知", "章程特殊规定"],
            weight=2.0
        ))

        # ============ 5. 劳动争议/仲裁 ============
        db.append(LitigationRule(
            id="labour_01", case_type_keywords=["劳动", "工伤", "工资"],
            scenario_scope=["pre_litigation", "defense", "arbitration"],
            category=RuleCategory.CLAIM,
            name="劳动关系确认审查",
            legal_source="《劳动合同法》",
            prompt_template="在无书面劳动合同情况下，审查事实劳动关系证据：{check_points}。",
            check_points=["工资支付记录", "社保缴纳记录", "工作证/工牌", "考勤记录"],
            weight=2.5
        ))

        # ============ 6. 证据通用规则 ============
        db.append(LitigationRule(
            id="evi_01", case_type_keywords=["general"],
            scenario_scope=["defense", "appeal"],
            category=RuleCategory.EVIDENCE,
            name="证据三性严格质证",
            legal_source="《民事诉讼法证据规定》",
            prompt_template="对对方核心证据进行三性打击：{check_points}。特别注意电子证据（微信/邮件）是否经过公证或具有完整性。",
            check_points=["真实性 (是否原件)", "合法性 (来源是否非法)", "关联性 (能否证明待证事实)"],
            weight=1.5
        ))

        return db