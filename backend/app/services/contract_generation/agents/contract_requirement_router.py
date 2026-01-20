# backend/app/services/contract_generation/agents/contract_requirement_router.py
"""
合同需求路由器（第一层判断）

核心功能：
判断用户需求是"单一合同"、"合同变更"、"合同解除"还是"合同规划"

判断逻辑（优先级从高到低）：
1. 合同变更（最高优先级）- 检测明确的变更关键词
2. 合同解除（高优先级）- 检测明确的解除关键词
3. 合同规划（中优先级）- 检测明确的规划关键词
4. 单一合同（默认）
5. 法律特征提取（模糊场景）
"""

import logging
import re
from typing import Dict, Any, List
from langchain_openai import ChatOpenAI

from .models import RequirementRoutingResult, RequirementType
from .complexity_analyzer import get_complexity_analyzer

try:
    from ..skills.legal_features_extraction_skill import (
        get_legal_features_extraction_skill,
        LegalFeaturesExtractionResult,
    )
    FEATURE_EXTRACTION_AVAILABLE = True
except ImportError:
    FEATURE_EXTRACTION_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("[ContractRequirementRouter] 法律特征提取技能不可用")

logger = logging.getLogger(__name__)


# ==================== 明确关键词定义（优化版）====================

# 【高优先级】合同变更类关键词 - 使用完整词组避免误判
CONTRACT_MODIFICATION_KEYWORDS = [
    "变更合同", "修改合同", "补充合同", "修订合同", "调整合同",
    "协议变更", "协议修改", "协议补充", "协议修订",
    "合同变更", "合同修改", "合同补充", "合同修订",
    # 保留单字关键词但在 _has_exact_keywords 中进行边界检查
    " 变更 ", " 修改 ", " 补充 ", " 修订 ", " 调整 ",
]

# 【高优先级】合同解除类关键词
CONTRACT_TERMINATION_KEYWORDS = [
    "解除合同", "终止合同", "撤销合同", "废止合同",
    "解除协议", "终止协议", "撤销协议", "废止协议",
    "合同解除", "合同终止", "合同撤销", "合同废止",
    # 保留单字关键词
    " 解除 ", " 终止 ", " 撤销 ", " 废止 ",
]

# 【中优先级】合同订立类关键词
CONTRACT_CREATION_KEYWORDS = [
    "订立", "签订", "签署", "起草", "拟定", "制定", "生成",
    "出具", "准备", "编制", "编写",
]

# 数量限定词（明确表示单一合同）
QUANTITY_KEYWORDS = [
    "一份合同", "一个协议", "本合同", "该合同", "原合同",
    "这份合同", "这份协议", "该协议",
]

# 合并单一合同关键词（不包含变更/解除）
SINGLE_CONTRACT_KEYWORDS = [
    *CONTRACT_CREATION_KEYWORDS,
    *QUANTITY_KEYWORDS,
]

# 【低优先级】合同规划关键词（优化后 - 移除容易误判的词）
# 移除了"系列"，因为在"系列分包合同"等场景中容易误判
CONTRACT_PLANNING_KEYWORDS = [
    "一揽子", "配套", "整体方案",
    "合同体系", "协议体系", "多份合同",
    "多个协议", "套装", "组合",
    # 【新增】添加常见的规划相关词汇
    " 规划协议", " 规划合同", "合同规划", "协议规划",
    " 整体规划", " 交易方案", " 文件包", "整套文件",
    " 分阶段", " 先.*再.*",  # 支持正则表达式
]


class ContractRequirementRouter:
    """
    合同需求路由器

    第一层判断：区分单一合同、合同变更、合同解除和合同规划

    优化版本（方案 A）：
    - 使用精确关键词匹配，优先判断变更/解除
    - 集成法律特征提取技能进行专业判断
    - 基于法律特征复杂度判断是否需要合同规划
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm
        self.complexity_analyzer = get_complexity_analyzer()
        self.feature_extraction_skill = None

        # 尝试初始化法律特征提取技能
        if FEATURE_EXTRACTION_AVAILABLE:
            try:
                self.feature_extraction_skill = get_legal_features_extraction_skill(llm)
                logger.info("[ContractRequirementRouter] 法律特征提取技能已启用")
            except Exception as e:
                logger.warning(f"[ContractRequirementRouter] 法律特征提取技能初始化失败: {e}")

    def route(
        self,
        user_input: str,
        context: Dict[str, Any] = None,
        use_feature_extraction: bool = True
    ) -> RequirementRoutingResult:
        """
        路由用户需求（优化版）

        判断优先级：
        1. 【新增】LLM 语义判断（最高优先级）- 使用 RequirementAnalyzer 判断所有四种类型
        2. 合同变更（高优先级）- 使用精确关键词（作为降级）
        3. 合同解除（高优先级）- 使用精确关键词（作为降级）
        4. 合同规划（中优先级）- 明确的规划指示词（作为降级）
        5. 单一合同（默认）

        Args:
            user_input: 用户的自然语言输入
            context: 额外上下文信息（可选）
            use_feature_extraction: 是否使用法律特征提取（默认 True）

        Returns:
            RequirementRoutingResult: 路由结果
        """
        try:
            logger.info(f"[ContractRequirementRouter] 开始路由用户需求: {user_input[:100]}")

            # ==================== 第一步：LLM 语义判断（新增）====================
            # 【新增】优先使用 RequirementAnalyzer 的 LLM 判断能力
            try:
                from .requirement_analyzer import RequirementAnalyzer
                analyzer = RequirementAnalyzer(llm=self.llm)

                # 使用 LLM 判断处理类型
                processing_type = analyzer._determine_processing_type(user_input)

                # 转换为 RequirementType
                processing_type_to_requirement = {
                    "contract_modification": RequirementType.CONTRACT_MODIFICATION,
                    "contract_termination": RequirementType.CONTRACT_TERMINATION,
                    "contract_planning": RequirementType.CONTRACT_PLANNING,
                    "single_contract": RequirementType.SINGLE_CONTRACT
                }

                requirement_type = processing_type_to_requirement.get(processing_type)

                if requirement_type:
                    logger.info(f"[ContractRequirementRouter] LLM 判断成功: {requirement_type}")

                    # 根据类型返回结果
                    if requirement_type == RequirementType.CONTRACT_MODIFICATION:
                        return RequirementRoutingResult(
                            requirement_type=requirement_type,
                            intent_description="用户需要变更已有合同",
                            confidence=0.95,
                            reasoning="LLM 语义分析：用户需求符合合同变更特征"
                        )
                    elif requirement_type == RequirementType.CONTRACT_TERMINATION:
                        return RequirementRoutingResult(
                            requirement_type=requirement_type,
                            intent_description="用户需要解除已有合同",
                            confidence=0.95,
                            reasoning="LLM 语义分析：用户需求符合合同解除特征"
                        )
                    elif requirement_type == RequirementType.CONTRACT_PLANNING:
                        return self._contract_planning_result(
                            user_input,
                            "LLM 语义分析：用户需求涉及多份合同或复杂交易结构"
                        )
                    else:  # SINGLE_CONTRACT
                        return self._single_contract_result(
                            user_input,
                            "LLM 语义分析：用户需求为单一合同"
                        )

            except Exception as llm_error:
                logger.warning(f"[ContractRequirementRouter] LLM 判断失败，使用关键词降级方案: {llm_error}")
                # 继续使用关键词匹配作为降级方案

            # ==================== 第二步：关键词匹配（降级方案）====================
            # 优先级1：合同变更（最高优先级）- 使用精确关键词
            if self._has_exact_keywords(user_input, CONTRACT_MODIFICATION_KEYWORDS):
                logger.info(f"[ContractRequirementRouter] 检测到合同变更关键词")
                return RequirementRoutingResult(
                    requirement_type=RequirementType.CONTRACT_MODIFICATION,
                    intent_description="用户需要变更已有合同",
                    confidence=0.95,
                    reasoning="用户输入包含明确的合同变更关键词"
                )

            # 优先级2：合同解除（高优先级）- 使用精确关键词
            if self._has_exact_keywords(user_input, CONTRACT_TERMINATION_KEYWORDS):
                logger.info(f"[ContractRequirementRouter] 检测到合同解除关键词")
                return RequirementRoutingResult(
                    requirement_type=RequirementType.CONTRACT_TERMINATION,
                    intent_description="用户需要解除已有合同",
                    confidence=0.95,
                    reasoning="用户输入包含明确的合同解除关键词"
                )

            # 优先级3：合同规划判断
            if self._has_exact_keywords(user_input, CONTRACT_PLANNING_KEYWORDS):
                logger.info(f"[ContractRequirementRouter] 检测到合同规划关键词")
                return self._contract_planning_result(
                    user_input,
                    "用户输入包含合同规划相关关键词"
                )

            # 优先级4：单一合同判断
            if self._has_exact_keywords(user_input, SINGLE_CONTRACT_KEYWORDS):
                logger.info(f"[ContractRequirementRouter] 检测到单一合同关键词")
                return self._single_contract_result(
                    user_input,
                    "用户输入包含明确单一合同关键词"
                )

            # ==================== 第三步：法律特征提取 ====================
            if use_feature_extraction and self.feature_extraction_skill:
                logger.info(f"[ContractRequirementRouter] 无明确关键词，调用法律特征提取")
                return self._route_by_feature_extraction(user_input, context)

            # ==================== 第四步：降级方案 ====================
            logger.info(f"[ContractRequirementRouter] 使用降级方案进行判断")
            return self._route_by_simple_rules(user_input)

        except Exception as e:
            logger.error(f"[ContractRequirementRouter] 路由失败: {str(e)}", exc_info=True)
            return RequirementRoutingResult(
                requirement_type=RequirementType.SINGLE_CONTRACT,
                intent_description="用户需求合同服务",
                confidence=0.5,
                reasoning="路由失败，使用默认类型"
            )

    def _has_exact_keywords(self, text: str, keywords: List[str]) -> bool:
        """
        检查文本是否包含精确关键词

        优化策略：
        1. 对于多字关键词（如"变更合同"），直接检查子串匹配
        2. 对于带空格的单字关键词（如" 变更 "），检查是否为独立词
        3. 【新增】对于包含 .* 的正则表达式模式，使用 re.search
        4. 避免部分匹配误判（如"系列分包"不应匹配"系列"）
        """
        for keyword in keywords:
            # 【新增】检查是否为正则表达式模式（包含 .*）
            if ".*" in keyword and not (keyword.startswith(" ") or keyword.endswith(" ")):
                # 去除首尾空格后作为正则表达式使用
                pattern = keyword.strip()
                if re.search(pattern, text):
                    logger.debug(f"[ContractRequirementRouter] 匹配正则表达式: {pattern}")
                    return True
                continue

            if keyword in text:
                # 如果关键词是带空格的单字，确保是完整词语
                if keyword.startswith(" ") and keyword.endswith(" "):
                    # 去掉空格后检查
                    clean_keyword = keyword.strip()
                    # 使用正则表达式确保是独立词语
                    pattern = rf'(?<!\w){clean_keyword}(?!\w)'
                    if re.search(pattern, text):
                        logger.debug(f"[ContractRequirementRouter] 匹配精确关键词: {clean_keyword}")
                        return True
                else:
                    # 多字关键词直接匹配
                    logger.debug(f"[ContractRequirementRouter] 匹配关键词: {keyword}")
                    return True
        return False

    def _route_by_feature_extraction(
        self,
        user_input: str,
        context: Dict[str, Any] = None
    ) -> RequirementRoutingResult:
        """
        使用法律特征提取进行路由

        Args:
            user_input: 用户输入
            context: 上下文信息

        Returns:
            RequirementRoutingResult: 路由结果
        """
        try:
            # 调用法律特征提取技能
            extraction_result: LegalFeaturesExtractionResult = self.feature_extraction_skill.extract_features(
                user_input,
                context
            )

            # 使用复杂度分析器判断
            needs_planning = self.complexity_analyzer.analyze(extraction_result)

            if needs_planning:
                # 获取规划原因
                planning_reasons = self.complexity_analyzer.get_planning_reasons(extraction_result)
                reasoning = "；".join(planning_reasons) if planning_reasons else "法律特征分析显示需要合同规划"

                return self._contract_planning_result(
                    user_input,
                    reasoning,
                    extraction_result
                )
            else:
                # 单一合同
                matched_types = extraction_result.matched_contract_types
                if matched_types:
                    reasoning = f"法律特征匹配：{matched_types[0]}"
                else:
                    reasoning = f"法律特征分析：{extraction_result.transaction_nature} - {extraction_result.contract_object}"

                return self._single_contract_result(
                    user_input,
                    reasoning,
                    extraction_result
                )

        except Exception as e:
            logger.error(f"[ContractRequirementRouter] 法律特征提取路由失败: {str(e)}", exc_info=True)
            # 降级到简单规则
            return self._route_by_simple_rules(user_input)

    def _route_by_simple_rules(self, user_input: str) -> RequirementRoutingResult:
        """
        使用简单规则进行路由（降级方案）

        Args:
            user_input: 用户输入

        Returns:
            RequirementRoutingResult: 路由结果
        """
        # 检查是否包含复杂交易的指示词
        complex_indicators = [
            ("投资", "经营"),
            ("转让", "许可"),
            ("股权", "技术"),
            ("合资", "开发"),
        ]

        for indicator1, indicator2 in complex_indicators:
            if indicator1 in user_input and indicator2 in user_input:
                return self._contract_planning_result(
                    user_input,
                    f"包含多种法律关系指示词：{indicator1} + {indicator2}"
                )

        # 默认为单一合同
        return self._single_contract_result(
            user_input,
            "未检测到复杂特征，默认为单一合同"
        )

    def _single_contract_result(
        self,
        user_input: str,
        reasoning: str,
        extraction_result: LegalFeaturesExtractionResult = None
    ) -> RequirementRoutingResult:
        """构建单一合同路由结果"""
        intent_desc = "用户需要单一合同服务"
        if extraction_result and extraction_result.matched_contract_types:
            intent_desc = f"用户需要：{extraction_result.matched_contract_types[0]}"

        return RequirementRoutingResult(
            requirement_type=RequirementType.SINGLE_CONTRACT,
            intent_description=intent_desc,
            confidence=0.9 if extraction_result else 0.7,
            reasoning=reasoning
        )

    def _contract_planning_result(
        self,
        user_input: str,
        reasoning: str,
        extraction_result: LegalFeaturesExtractionResult = None
    ) -> RequirementRoutingResult:
        """构建合同规划路由结果"""
        return RequirementRoutingResult(
            requirement_type=RequirementType.CONTRACT_PLANNING,
            intent_description="用户需要合同规划服务（多份合同组合）",
            confidence=0.9 if extraction_result else 0.7,
            reasoning=reasoning
        )


def get_contract_requirement_router(llm: ChatOpenAI) -> ContractRequirementRouter:
    """获取合同需求路由器实例"""
    return ContractRequirementRouter(llm)
