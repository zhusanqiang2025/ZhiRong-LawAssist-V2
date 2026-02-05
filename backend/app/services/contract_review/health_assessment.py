# backend/app/services/contract_review/health_assessment.py
"""
合同健康度综合评估服务

基于审查结果计算合同整体健康度评分
"""
from typing import List, Dict
from app.models.contract import ContractReviewItem
import logging

logger = logging.getLogger(__name__)


class ContractHealthAssessment:
    """合同健康度评估器"""

    # 严重程度扣分权重（标准化键名）
    # 使用递减权重，避免过多风险点导致分数过低
    SEVERITY_WEIGHTS = {
        "critical": 15,  # 从 30 降低到 15
        "high": 8,       # 从 20 降低到 8
        "medium": 3,     # 从 10 降低到 3
        "low": 1,        # 从 5 降低到 1
        # 兼容首字母大写格式
        "Critical": 15,
        "High": 8,
        "Medium": 3,
        "Low": 1
    }

    # 中文到英文的映射
    SEVERITY_ZH_TO_EN = {
        "极严重": "critical",
        "严重": "high",
        "中等": "medium",
        "轻微": "low",
        "高": "high",
        "中": "medium",
        "低": "low"
    }

    # 风险等级阈值
    RISK_LEVELS = {
        "健康": 90,
        "良好": 70,
        "中等风险": 50,
        "高风险": 30,
        "极高风险": 0
    }

    def _normalize_severity(self, severity: str) -> str:
        """
        标准化 severity 值

        处理各种可能的输入格式：
        - 英文：Critical, High, Medium, Low
        - 中文：极严重, 严重, 中等, 轻微
        - 小写：critical, high, medium, low
        """
        if not severity:
            return "medium"

        # 先转为字符串并去除首尾空格
        severity = str(severity).strip()

        # 如果已经是标准格式（首字母大写），直接返回
        if severity in self.SEVERITY_WEIGHTS:
            return severity

        # 尝试中文映射
        if severity in self.SEVERITY_ZH_TO_EN:
            return self.SEVERITY_ZH_TO_EN[severity].capitalize()

        # 尝试小写格式
        severity_lower = severity.lower()
        for key in self.SEVERITY_WEIGHTS:
            if key.lower() == severity_lower:
                return key

        # 默认返回 medium
        logger.warning(f"无法识别的 severity 值: '{severity}'，使用默认值 'Medium'")
        return "Medium"

    def calculate_health_score(self, review_items: List[ContractReviewItem]) -> Dict:
        """
        计算合同健康度评分

        Args:
            review_items: 审查风险点列表

        Returns:
            健康度评估结果 {
                "score": 55,  # 0-100
                "level": "高风险",
                "summary": "该合同风险较高...",
                "risk_distribution": {...},
                "total_risks": 10,
                "recommendations": [...]
            }
        """
        if not review_items:
            return {
                "score": 100,
                "level": "健康",
                "summary": "合同审查未发现风险点，整体健康度良好。",
                "risk_distribution": {
                    "Critical": 0,
                    "High": 0,
                    "Medium": 0,
                    "Low": 0
                },
                "total_risks": 0,
                "recommendations": []
            }

        # 1. 基础分 100 分
        base_score = 100

        # 2. 按严重程度扣分
        total_deduction = 0
        risk_distribution = {
            "Critical": 0,
            "High": 0,
            "Medium": 0,
            "Low": 0
        }

        for item in review_items:
            severity_raw = item.severity
            # 标准化 severity 值
            severity = self._normalize_severity(severity_raw)
            # 记录实际的 severity 值用于调试
            if severity_raw != severity:
                logger.info(f"[HealthAssessment] severity 规范化: '{severity_raw}' -> '{severity}'")
            if severity in self.SEVERITY_WEIGHTS:
                total_deduction += self.SEVERITY_WEIGHTS[severity]
                risk_distribution[severity] += 1
            else:
                logger.warning(f"未知的严重程度: '{severity}' (期望值: {list(self.SEVERITY_WEIGHTS.keys())})")

        # 3. 改进的评分算法：使用非线性扣分，避免风险点过多导致分数过低
        # 基础分 100 分，使用平方根函数平滑扣分
        import math
        if total_deduction > 0:
            # 使用平方根函数平滑扣分：√(扣分) * 系数
            # 这样即使有很多风险点，分数也不会过低
            smooth_deduction = math.sqrt(total_deduction) * 8
            final_score = max(0, min(100, base_score - smooth_deduction))
        else:
            final_score = 100

        logger.info(
            f"[HealthAssessment] 评分详情: 总扣分={total_deduction}, 平滑扣分={smooth_deduction:.1f}, 最终分数={final_score:.1f}"
        )

        # 4. 确定风险等级
        level = self._get_risk_level(final_score)

        # 5. 生成综合评语
        summary = self._generate_summary(review_items, final_score, level)

        # 6. 生成改进建议
        recommendations = self._generate_recommendations(review_items)

        # 7. 四舍五入分数为整数
        final_score_int = int(round(final_score))

        logger.info(
            f"[HealthAssessment] 计算完成 - 分数: {final_score_int}, "
            f"等级: {level}, 风险点: {len(review_items)}"
        )

        return {
            "score": final_score_int,
            "level": level,
            "summary": summary,
            "risk_distribution": risk_distribution,
            "total_risks": len(review_items),
            "recommendations": recommendations
        }

    def _get_risk_level(self, score: int) -> str:
        """根据分数确定风险等级"""
        if score >= self.RISK_LEVELS["健康"]:
            return "健康"
        elif score >= self.RISK_LEVELS["良好"]:
            return "良好"
        elif score >= self.RISK_LEVELS["中等风险"]:
            return "中等风险"
        elif score >= self.RISK_LEVELS["高风险"]:
            return "高风险"
        else:
            return "极高风险"

    def _generate_summary(
        self,
        review_items: List[ContractReviewItem],
        score: int,
        level: str
    ) -> str:
        """生成综合评语"""
        # 统计关键信息（使用规范化后的 severity）
        total = len(review_items)
        critical = sum(1 for r in review_items if self._normalize_severity(r.severity) == "Critical")
        high = sum(1 for r in review_items if self._normalize_severity(r.severity) == "High")

        # 按问题类型分组
        issue_types = {}
        for item in review_items:
            # 提取问题类型（去掉详细分类）
            issue_type = item.issue_type.split('-')[0] if '-' in item.issue_type else item.issue_type
            issue_types[issue_type] = issue_types.get(issue_type, 0) + 1

        # 生成评语文本
        if level == "极高风险":
            summary = f"该合同存在{total}处重大风险（{critical}处极严重、{high}处高风险），"
        elif level == "高风险":
            summary = f"该合同风险较高，存在{total}处风险点（{critical}处极严重、{high}处高风险），"
        elif level == "中等风险":
            summary = f"该合同存在{total}处风险点（{critical}处极严重、{high}处高风险），"
        else:
            summary = f"该合同整体风险较低，存在{total}处轻微风险点，"

        # 主要问题领域
        if issue_types:
            top_issues = sorted(issue_types.items(), key=lambda x: x[1], reverse=True)[:3]
            issue_names = "、".join([name for name, count in top_issues])
            summary += f"尤其在{issue_names}方面需要重点关注。"

        # 修改建议
        if level in ["极高风险", "高风险"]:
            summary += "强烈建议在签约前进行重大修改。"
        elif level == "中等风险":
            summary += "建议对关键条款进行修改后再签约。"
        else:
            summary += "建议对提示的条款进行适当调整。"

        return summary

    def _generate_recommendations(
        self,
        review_items: List[ContractReviewItem]
    ) -> List[str]:
        """生成改进建议"""
        recommendations = []

        # 统计最常见的问题类型
        issue_count = {}
        for item in review_items:
            issue_type = item.issue_type
            issue_count[issue_type] = issue_count.get(issue_type, 0) + 1

        # 基于问题类型生成建议
        issue_count_str = str(issue_count)

        if "违约责任" in issue_count_str:
            recommendations.append("明确违约责任的计算方式和上限，避免责任过重")

        if "争议解决" in issue_count_str:
            recommendations.append("优化争议解决条款，选择合适的管辖法院")

        if "预付款" in issue_count_str:
            recommendations.append("调整预付款比例，不超过合同总价的30%")

        if "解除" in issue_count_str:
            recommendations.append("完善合同解除条件，确保双方权利义务对等")

        if "验收" in issue_count_str:
            recommendations.append("明确验收标准和程序，避免歧义")

        # 根据严重程度添加建议（使用规范化后的 severity）
        critical_count = sum(1 for r in review_items if self._normalize_severity(r.severity) == "Critical")
        if critical_count > 0:
            recommendations.append(f"优先处理 {critical_count} 处极严重风险点")

        high_count = sum(1 for r in review_items if self._normalize_severity(r.severity) == "High")
        if high_count > 2:
            recommendations.append(f"高风险点较多（{high_count}处），建议全面审查合同")

        return recommendations


# 单例模式
contract_health_assessor = ContractHealthAssessment()
