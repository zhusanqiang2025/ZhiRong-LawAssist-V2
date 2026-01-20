# backend/app/services/contract_generation/strategy/generation_strategy.py
"""
生成策略选择服务

这是第三层：Generation Strategy Layer（生成策略选择层）

核心设计原则：
- 高度匹配模板（≥0.75）→ 模板填充 + AI 审查
- 结构一致模板（0.4–0.75）→ 生成新合同 + 模块对照
- 无模板 → 纯条款骨架生成

这层是"成熟系统"和"玩具系统"的分水岭。
"""
import logging
import os
from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class GenerationType(Enum):
    """合同生成类型"""
    # 基于模板填充
    TEMPLATE_BASED = "template_based"
    # 混合模式：生成新合同 + 模板对照
    HYBRID = "hybrid"
    # 纯 AI 生成（条款骨架）
    AI_GENERATED = "ai_generated"
    # ✨ 新增：两阶段 AI 生成（框架 + 填充）
    AI_TWO_STAGE = "ai_two_stage"


@dataclass
class GenerationStrategy:
    """
    生成策略

    包含：
    - generation_type: 生成类型
    - template_id: 使用的模板 ID（如果有）
    - reasoning: 策略选择原因
    - expected_quality: 预期质量评分
    - requires_review: 是否需要人工审查
    - use_two_stage: 是否使用两阶段生成（仅 AI_TWO_STAGE 时为 True）
    - framework_model: 框架生成模型名称（仅两阶段生成）
    - filling_model: 内容填充模型名称（仅两阶段生成）
    """
    generation_type: GenerationType
    template_id: Optional[str]
    template_name: Optional[str]
    reasoning: str
    expected_quality: float  # 0-1
    requires_review: bool
    # ✨ 新增：两阶段生成配置
    use_two_stage: bool = False
    framework_model: Optional[str] = None
    filling_model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "generation_type": self.generation_type.value,
            "template_id": self.template_id,
            "template_name": self.template_name,
            "reasoning": self.reasoning,
            "expected_quality": self.expected_quality,
            "requires_review": self.requires_review,
            "use_two_stage": self.use_two_stage,
            "framework_model": self.framework_model,
            "filling_model": self.filling_model,
        }


class GenerationStrategySelector:
    """
    生成策略选择器

    基于第二层（Structural Template Matcher）的输出，
    选择最合适的生成策略。
    """

    def __init__(self):
        """初始化策略选择器"""
        logger.info("[GenerationStrategySelector] 初始化完成")

    def select_strategy(
        self,
        match_result: Dict[str, Any],
        analysis_result: Dict[str, Any]
    ) -> GenerationStrategy:
        """
        选择生成策略

        Args:
            match_result: StructuralTemplateMatcher 的输出
            analysis_result: RequirementAnalyzer 的输出

        Returns:
            GenerationStrategy: 选择的生成策略
        """
        match_level = match_result.get("match_level")
        template_id = match_result.get("template_id")
        template_name = match_result.get("template_name")

        # 提取风险等级
        transaction_structure = analysis_result.get("transaction_structure", {})
        risk_level = transaction_structure.get("risk_level", "中")

        # 策略 1：高度匹配（HIGH）→ 模板填充 + AI 审查
        if match_level == "high":
            logger.info(f"[GenerationStrategySelector] 选择策略 1：模板填充（模板：{template_name}）")

            return GenerationStrategy(
                generation_type=GenerationType.TEMPLATE_BASED,
                template_id=template_id,
                template_name=template_name,
                reasoning=f"找到高度匹配的模板（{template_name}），将使用模板填充方式生成合同，并进行 AI 审查以确保合规性。",
                expected_quality=0.85,
                requires_review=(risk_level == "高")  # 高风险交易需要人工审查
            )

        # 策略 2：结构一致（STRUCTURAL）→ 生成新合同 + 模板对照
        elif match_level == "structural":
            logger.info(f"[GenerationStrategySelector] 选择策略 2：混合模式（模板：{template_name}）")

            structural_diffs = match_result.get("structural_differences", [])

            return GenerationStrategy(
                generation_type=GenerationType.HYBRID,
                template_id=template_id,
                template_name=template_name,
                reasoning=f"找到结构类似的模板（{template_name}），但由于结构差异（{', '.join(structural_diffs)}），将采用「生成新合同 + 模板对照」的方式。",
                expected_quality=0.75,
                requires_review=True  # 混合模式始终需要审查
            )

        # 策略 3：无模板（NONE）→ 纯条款骨架生成或两阶段生成
        else:
            # ✨ 检查是否启用两阶段生成
            use_two_stage = os.getenv("ENABLE_TWO_STAGE_GENERATION", "false").lower() == "true"

            # 提取合同类型和不匹配原因
            mismatch_reasons = match_result.get("mismatch_reasons", [])
            contract_classification = analysis_result.get("contract_classification", {})
            primary_type = contract_classification.get("primary_type", "合同")

            if use_two_stage:
                logger.info("[GenerationStrategySelector] 选择策略 3b：两阶段 AI 生成（无模板）")

                # 验证两阶段生成所需的模型配置
                try:
                    from app.core.llm_config import validate_llm_config
                    config = validate_llm_config()

                    if not config.get("two_stage_ready"):
                        logger.warning("[GenerationStrategySelector] 两阶段生成配置不完整，降级到单次生成")
                        logger.warning(f"[GenerationStrategySelector] 配置状态: qwen3={config.get('qwen3_thinking')}, deepseek={config.get('deepseek')}")
                        use_two_stage = False
                except Exception as e:
                    logger.warning(f"[GenerationStrategySelector] 无法验证两阶段配置: {e}，降级到单次生成")
                    use_two_stage = False

            if use_two_stage:
                # 两阶段生成策略
                return GenerationStrategy(
                    generation_type=GenerationType.AI_TWO_STAGE,
                    template_id=None,
                    template_name=None,
                    reasoning=f"未找到合适的模板（原因：{', '.join(mismatch_reasons)}）。将采用「两阶段生成」策略：第一阶段使用 Qwen3-235B-Thinking 生成合同框架，第二阶段使用 DeepSeek-R1-0528 填充具体条款内容，确保结构完整性和内容质量。",
                    expected_quality=0.72,  # 高于单次生成
                    requires_review=True,
                    use_two_stage=True,
                    framework_model="Qwen3-235B-Thinking",
                    filling_model="DeepSeek-R1-0528"
                )
            else:
                # 单次 AI 生成策略（原有逻辑）
                logger.info("[GenerationStrategySelector] 选择策略 3a：单次 AI 生成（无模板）")

                return GenerationStrategy(
                    generation_type=GenerationType.AI_GENERATED,
                    template_id=None,
                    template_name=None,
                    reasoning=f"未找到合适的模板（原因：{', '.join(mismatch_reasons)}）。将基于 {primary_type} 的法律要素，纯 AI 生成条款骨架。",
                    expected_quality=0.65,
                    requires_review=True  # 纯 AI 生成始终需要审查
                )

    def should_use_template(
        self,
        match_result: Dict[str, Any]
    ) -> bool:
        """
        判断是否应该使用模板

        这是一个简化的决策函数，用于快速判断。

        Args:
            match_result: 匹配结果

        Returns:
            bool: 是否使用模板
        """
        match_level = match_result.get("match_level")
        return match_level in ("high", "structural")

    def get_template_usage_confidence(
        self,
        match_result: Dict[str, Any]
    ) -> float:
        """
        获取模板使用的置信度

        Args:
            match_result: 匹配结果

        Returns:
            float: 置信度（0-1）
        """
        match_level = match_result.get("match_level")

        if match_level == "high":
            return 0.9
        elif match_level == "structural":
            return 0.6
        else:
            return 0.0


# ==================== 单例模式 ====================

_strategy_selector_instance: Optional[GenerationStrategySelector] = None


def get_strategy_selector() -> GenerationStrategySelector:
    """
    获取策略选择器单例

    Returns:
        GenerationStrategySelector: 策略选择器实例
    """
    global _strategy_selector_instance
    if _strategy_selector_instance is None:
        _strategy_selector_instance = GenerationStrategySelector()
    return _strategy_selector_instance
