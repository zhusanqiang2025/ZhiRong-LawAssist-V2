# backend/app/services/contract_generation/agents/complexity_analyzer.py
"""
合同复杂度分析器

核心功能：
分析法律特征的复杂程度，判断是否需要合同规划。

判断规则：
1. 多个不同的交易性质 → 需要规划
2. 多种标的类型 → 需要规划
3. 特殊的复杂交易性质 → 需要规划
4. 交易特征描述复杂 → 需要规划
"""

import logging
from typing import List

# 不再需要导入枚举类，数据库版本使用字符串值
# 保留备用定义以兼容旧代码
class TransactionNature(str):
    ASSET_TRANSFER = "ASSET_TRANSFER"
    SERVICE_DELIVERY = "SERVICE_DELIVERY"
    AUTHORIZATION = "AUTHORIZATION"
    ENTITY_CREATION = "ENTITY_CREATION"
    CAPITAL_FINANCE = "CAPITAL_FINANCE"
    LABOR_EMPLOYMENT = "LABOR_EMPLOYMENT"
    DISPUTE_RESOLUTION = "DISPUTE_RESOLUTION"

from ..skills.legal_features_extraction_skill import LegalFeaturesExtractionResult

logger = logging.getLogger(__name__)


class ComplexityAnalyzer:
    """
    合同复杂度分析器

    根据提取的法律特征判断是否需要合同规划
    """

    # 特殊的复杂交易性质
    COMPLEX_NATURES = [
        "ENTITY_CREATION",  # 合作经营
        "CAPITAL_FINANCE",  # 融资借贷（股权交易等）
    ]

    # 复杂特征指示词对
    COMPLEX_INDICATORS = [
        ("投资", "经营"),  # 既投资又经营
        ("转让", "许可"),  # 既转让又许可
        ("服务", "货物"),  # 既有服务又有货物
        ("股权", "技术"),  # 既涉及股权又涉及技术
        ("资金", "资产"),  # 既涉及资金又涉及资产
        ("开发", "许可"),  # 既开发又许可
        ("销售", "服务"),  # 既销售又服务
        ("合作", "转让"),  # 既合作又转让
    ]

    def analyze(self, extraction_result: LegalFeaturesExtractionResult) -> bool:
        """
        判断是否需要合同规划

        Args:
            extraction_result: 法律特征提取结果

        Returns:
            bool: True 表示需要合同规划，False 表示单一合同
        """
        detected_natures = extraction_result.complexity_analysis.detected_natures
        detected_objects = extraction_result.complexity_analysis.detected_objects
        characteristics = extraction_result.transaction_characteristics

        logger.info(f"[ComplexityAnalyzer] 开始分析复杂度")
        logger.info(f"  - 检测到的交易性质: {detected_natures}")
        logger.info(f"  - 检测到的合同标的: {detected_objects}")

        # 规则1：多个不同的交易性质 → 需要规划
        if len(detected_natures) > 1:
            logger.info(f"[ComplexityAnalyzer] 规则1匹配：多个交易性质 → 需要规划")
            return True

        # 规则2：涉及多种标的类型 → 需要规划
        if len(detected_objects) > 1:
            logger.info(f"[ComplexityAnalyzer] 规则2匹配：多种标的类型 → 需要规划")
            return True

        # 规则3：特殊的复杂交易性质 → 需要规划
        if any(nature in self.COMPLEX_NATURES for nature in detected_natures):
            logger.info(f"[ComplexityAnalyzer] 规则3匹配：检测到复杂交易性质 → 需要规划")
            return True

        # 规则4：交易特征描述复杂（包含多个不同类型的描述）
        if self._has_complex_characteristics(characteristics):
            logger.info(f"[ComplexityAnalyzer] 规则4匹配：交易特征描述复杂 → 需要规划")
            return True

        logger.info(f"[ComplexityAnalyzer] 单一特征 → 单一合同")
        return False

    def _has_complex_characteristics(self, characteristics: str) -> bool:
        """
        检查交易特征描述是否包含多个不同类型

        Args:
            characteristics: 交易特征描述

        Returns:
            bool: True 表示包含复杂特征，False 表示单一特征
        """
        if not characteristics:
            return False

        for indicator1, indicator2 in self.COMPLEX_INDICATORS:
            if indicator1 in characteristics and indicator2 in characteristics:
                logger.info(f"[ComplexityAnalyzer] 检测到复杂指示词: ({indicator1}, {indicator2})")
                return True

        return False

    def get_planning_reasons(
        self,
        extraction_result: LegalFeaturesExtractionResult
    ) -> List[str]:
        """
        获取需要合同规划的原因

        Args:
            extraction_result: 法律特征提取结果

        Returns:
            List[str]: 规划原因列表
        """
        reasons = []
        detected_natures = extraction_result.complexity_analysis.detected_natures
        detected_objects = extraction_result.complexity_analysis.detected_objects
        characteristics = extraction_result.transaction_characteristics

        # 检查交易性质
        if len(detected_natures) > 1:
            nature_labels = self._get_nature_labels(detected_natures)
            reasons.append(f"涉及多种交易性质：{', '.join(nature_labels)}")
        elif detected_natures and detected_natures[0] in self.COMPLEX_NATURES:
            nature_label = self._get_nature_label(detected_natures[0])
            reasons.append(f"涉及复杂交易类型：{nature_label}")

        # 检查合同标的
        if len(detected_objects) > 1:
            object_labels = self._get_object_labels(detected_objects)
            reasons.append(f"涉及多种合同标的：{', '.join(object_labels)}")

        # 检查复杂指示词
        for indicator1, indicator2 in self.COMPLEX_INDICATORS:
            if indicator1 in characteristics and indicator2 in characteristics:
                reasons.append(f"交易描述包含多种法律关系（{indicator1} + {indicator2}）")
                break

        return reasons

    def _get_nature_label(self, nature: str) -> str:
        """获取交易性质的中文标签"""
        labels = {
            "ASSET_TRANSFER": "转移所有权",
            "SERVICE_DELIVERY": "提供服务",
            "AUTHORIZATION": "许可使用",
            "ENTITY_CREATION": "合作经营",
            "CAPITAL_FINANCE": "融资借贷",
            "LABOR_EMPLOYMENT": "劳动用工",
            "DISPUTE_RESOLUTION": "争议解决",
        }
        return labels.get(nature, nature)

    def _get_nature_labels(self, natures: List[str]) -> List[str]:
        """获取多个交易性质的中文标签"""
        return [self._get_nature_label(nature) for nature in natures]

    def _get_object_label(self, obj: str) -> str:
        """获取合同标的的中文标签"""
        labels = {
            "TANGIBLE_GOODS": "货物",
            "PROJECT": "工程",
            "IP": "智力成果",
            "SERVICE": "服务",
            "EQUITY": "股权",
            "MONETARY_DEBT": "资金",
            "HUMAN_LABOR": "劳动力",
            "REAL_ESTATE": "不动产",
            "MOVABLE_PROPERTY": "动产",
        }
        return labels.get(obj, obj)

    def _get_object_labels(self, objects: List[str]) -> List[str]:
        """获取多个合同标的的中文标签"""
        return [self._get_object_label(obj) for obj in objects]


def get_complexity_analyzer() -> ComplexityAnalyzer:
    """获取复杂度分析器实例"""
    return ComplexityAnalyzer()
