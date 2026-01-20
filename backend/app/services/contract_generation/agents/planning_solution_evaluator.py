# backend/app/services/contract_generation/agents/planning_solution_evaluator.py
"""
方案评审服务

核心功能：
评估多个模型输出的合同规划方案，选择最优方案

评估维度：
1. 完整性 (25%) - 是否覆盖所有必要的合同类型
2. 逻辑性 (30%) - 合同间依赖关系是否合理
3. 风险识别 (25%) - 是否识别并规避潜在风险
4. 可执行性 (20%) - 规划是否切实可行
"""

import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EvaluationDimension(Enum):
    """评估维度"""
    COMPLETENESS = "completeness"      # 完整性
    LOGIC = "logic"                    # 逻辑性
    RISK_IDENTIFICATION = "risk"       # 风险识别
    EXECUTABILITY = "executability"    # 可执行性


@dataclass
class EvaluationScore:
    """评估分数"""
    dimension: EvaluationDimension
    weight: float  # 权重
    score: float   # 分数 (0-100)
    reason: str    # 评分理由

    @property
    def weighted_score(self) -> float:
        """加权分数"""
        return self.score * self.weight


@dataclass
class SolutionEvaluation:
    """方案评估结果"""
    model_name: str
    total_score: float  # 总分 (0-100)
    dimension_scores: List[EvaluationScore]
    comments: str  # 综合评价
    rank: int = 0  # 排名（后续填充）


class PlanningSolutionEvaluator:
    """
    方案评审服务

    评估多个合同规划方案，选择最优
    """

    # 评估维度权重配置
    DIMENSION_WEIGHTS = {
        EvaluationDimension.COMPLETENESS: 0.25,
        EvaluationDimension.LOGIC: 0.30,
        EvaluationDimension.RISK_IDENTIFICATION: 0.25,
        EvaluationDimension.EXECUTABILITY: 0.20,
    }

    def __init__(self, llm: Optional[ChatOpenAI] = None):
        """
        初始化评审服务

        Args:
            llm: 用于评审的 LLM（可选，不提供则使用规则评分）
        """
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

    def evaluate(
        self,
        solutions: List[Dict[str, Any]],
        user_input: str
    ) -> List[SolutionEvaluation]:
        """
        评估多个方案

        Args:
            solutions: 方案列表，每个方案包含 model_name 和 planning_data
            user_input: 用户原始输入（用于上下文）

        Returns:
            List[SolutionEvaluation]: 评估结果列表，按总分降序排列
        """
        logger.info(f"[SolutionEvaluator] 开始评估 {len(solutions)} 个方案")

        evaluations = []

        for solution in solutions:
            model_name = solution.get("model_name", "unknown")
            planning_data = solution.get("planning_data", {})

            evaluation = self._evaluate_single_solution(
                model_name=model_name,
                planning_data=planning_data,
                user_input=user_input
            )

            evaluations.append(evaluation)

        # 排序并添加排名
        evaluations.sort(key=lambda e: e.total_score, reverse=True)
        for idx, eval in enumerate(evaluations, 1):
            eval.rank = idx

        logger.info(f"[SolutionEvaluator] 评估完成，最佳方案: {evaluations[0].model_name} (分数: {evaluations[0].total_score:.2f})")

        return evaluations

    def _evaluate_single_solution(
        self,
        model_name: str,
        planning_data: Dict[str, Any],
        user_input: str
    ) -> SolutionEvaluation:
        """
        评估单个方案

        Args:
            model_name: 模型名称
            planning_data: 规划数据
            user_input: 用户输入

        Returns:
            SolutionEvaluation: 评估结果
        """
        contracts = planning_data.get("contracts", [])
        signing_order = planning_data.get("signing_order", [])
        relationships = planning_data.get("relationships", {})
        risk_notes = planning_data.get("risk_notes", [])
        overall_description = planning_data.get("overall_description", "")

        dimension_scores = []

        # 评估各个维度
        for dimension, weight in self.DIMENSION_WEIGHTS.items():
            score, reason = self._score_dimension(
                dimension=dimension,
                contracts=contracts,
                signing_order=signing_order,
                relationships=relationships,
                risk_notes=risk_notes,
                overall_description=overall_description,
                user_input=user_input
            )

            dimension_scores.append(EvaluationScore(
                dimension=dimension,
                weight=weight,
                score=score,
                reason=reason
            ))

        # 计算总分
        total_score = sum(dscore.weighted_score for dscore in dimension_scores)

        # 生成综合评价
        comments = self._generate_comments(dimension_scores, planning_data)

        return SolutionEvaluation(
            model_name=model_name,
            total_score=total_score,
            dimension_scores=dimension_scores,
            comments=comments
        )

    def _score_dimension(
        self,
        dimension: EvaluationDimension,
        contracts: List[Dict],
        signing_order: List[str],
        relationships: Dict,
        risk_notes: List[str],
        overall_description: str,
        user_input: str
    ) -> tuple[float, str]:
        """
        对单个维度进行评分

        Args:
            dimension: 评估维度
            contracts: 合同列表
            signing_order: 签署顺序
            relationships: 关系映射
            risk_notes: 风险提示
            overall_description: 整体描述
            user_input: 用户输入

        Returns:
            tuple: (分数 0-100, 评分理由)
        """
        if dimension == EvaluationDimension.COMPLETENESS:
            return self._score_completeness(contracts, user_input)

        elif dimension == EvaluationDimension.LOGIC:
            return self._score_logic(contracts, signing_order, relationships)

        elif dimension == EvaluationDimension.RISK_IDENTIFICATION:
            return self._score_risk_identification(contracts, risk_notes)

        elif dimension == EvaluationDimension.EXECUTABILITY:
            return self._score_executability(contracts, signing_order, overall_description)

        else:
            return 50.0, "未知维度"

    def _score_completeness(self, contracts: List[Dict], user_input: str) -> tuple[float, str]:
        """
        评估完整性

        评分标准：
        - 合同数量是否合理（1-5份为佳）
        - 是否包含必要的合同类型（主协议、配套协议）
        - 是否覆盖主要法律关系
        """
        contract_count = len(contracts)

        # 基础分数
        if 2 <= contract_count <= 4:
            score = 90.0
            reason = f"包含 {contract_count} 份合同，数量合理"
        elif contract_count == 1:
            score = 60.0
            reason = "仅包含 1 份合同，可能不够全面"
        elif 5 <= contract_count <= 6:
            score = 75.0
            reason = f"包含 {contract_count} 份合同，较为详细"
        else:
            score = 50.0
            reason = f"包含 {contract_count} 份合同，可能过于复杂或分散"

        # 检查是否包含主协议
        has_main_contract = any(
            c.get("priority", 99) == 1 or
            any(keyword in c.get("title", "").lower() for keyword in ["协议", "合同", "主协议", "框架协议"])
            for c in contracts
        )

        if has_main_contract:
            score += 5.0
            reason += "，包含明确的主协议"
        else:
            score -= 10.0
            reason += "，缺少明确的主协议"

        # 检查合同目的描述
        has_purpose = any(c.get("purpose") for c in contracts)
        if has_purpose:
            score += 5.0
            reason += "，合同目的描述清晰"
        else:
            score -= 5.0
            reason += "，合同目的描述不足"

        return min(max(score, 0), 100), reason

    def _score_logic(self, contracts: List[Dict], signing_order: List[str], relationships: Dict) -> tuple[float, str]:
        """
        评估逻辑性

        评分标准：
        - 签署顺序是否合理
        - 依赖关系是否清晰
        - 合同优先级是否正确
        """
        score = 70.0
        reasons = []

        # 检查签署顺序
        if signing_order and len(signing_order) == len(contracts):
            score += 15.0
            reasons.append("签署顺序完整")
        else:
            score -= 10.0
            reasons.append("签署顺序不完整或与合同数量不符")

        # 检查优先级设置
        priorities = [c.get("priority", 0) for c in contracts]
        if priorities and len(set(priorities)) == len(priorities):
            score += 10.0
            reasons.append("优先级设置合理且不重复")
        else:
            score -= 5.0
            reasons.append("优先级设置存在问题")

        # 检查依赖关系
        if relationships:
            score += 5.0
            reasons.append("合同依赖关系描述清晰")
        else:
            score -= 5.0
            reasons.append("缺少合同依赖关系描述")

        # 检查循环依赖
        if self._has_circular_dependency(relationships):
            score -= 20.0
            reasons.append("存在循环依赖，逻辑有误")
        else:
            score += 5.0
            reasons.append("无循环依赖")

        return min(max(score, 0), 100), "，".join(reasons)

    def _score_risk_identification(self, contracts: List[Dict], risk_notes: List[str]) -> tuple[float, str]:
        """
        评估风险识别

        评分标准：
        - 是否识别了关键风险点
        - 风险提示数量是否合理
        - 风险提示是否具体
        """
        score = 50.0
        reasons = []

        if risk_notes:
            risk_count = len(risk_notes)
            if 2 <= risk_count <= 5:
                score += 30.0
                reasons.append(f"识别了 {risk_count} 个关键风险点")
            elif risk_count == 1:
                score += 10.0
                reasons.append("识别了 1 个风险点，可能不够全面")
            elif risk_count > 5:
                score += 20.0
                reasons.append(f"识别了 {risk_count} 个风险点，较为详细")
        else:
            score -= 10.0
            reasons.append("未识别风险点")

        # 检查风险提示的具体性
        has_specific_risk = any(len(note) > 10 for note in risk_notes)
        if has_specific_risk:
            score += 10.0
            reasons.append("风险提示描述具体")
        else:
            score -= 5.0
            reasons.append("风险提示描述过于笼统")

        # 检查是否考虑了风险隔离
        has_risk_isolation = any(
            "隔离" in c.get("purpose", "").lower() or
            "独立" in c.get("purpose", "").lower()
            for c in contracts
        )
        if has_risk_isolation:
            score += 10.0
            reasons.append("考虑了风险隔离")

        return min(max(score, 0), 100), "，".join(reasons)

    def _score_executability(self, contracts: List[Dict], signing_order: List[str], overall_description: str) -> tuple[float, str]:
        """
        评估可执行性

        评分标准：
        - 规划是否切实可行
        - 整体描述是否清晰
        - 合同章节预估是否合理
        """
        score = 60.0
        reasons = []

        # 检查整体描述
        if overall_description and len(overall_description) > 20:
            score += 20.0
            reasons.append("整体交易结构描述清晰")
        else:
            score -= 10.0
            reasons.append("整体交易结构描述不足")

        # 检查合同章节预估
        has_estimated_sections = any(
            c.get("estimated_sections") for c in contracts
        )
        if has_estimated_sections:
            score += 10.0
            reasons.append("合同章节预估合理")
        else:
            score -= 5.0
            reasons.append("缺少合同章节预估")

        # 检查签署顺序的可执行性
        if signing_order and len(signing_order) > 1:
            # 检查是否有依赖未签署的合同
            dependencies_ok = True
            for i, contract_id in enumerate(signing_order):
                contract = next((c for c in contracts if c.get("id") == contract_id), None)
                if contract:
                    deps = contract.get("dependencies", [])
                    for dep in deps:
                        if dep not in signing_order[:i]:
                            dependencies_ok = False
                            break

            if dependencies_ok:
                score += 10.0
                reasons.append("签署顺序可执行")
            else:
                score -= 15.0
                reasons.append("签署顺序存在依赖问题")

        # 检查合同主体是否明确
        has_key_parties = any(
            c.get("key_parties") and len(c.get("key_parties", [])) >= 2
            for c in contracts
        )
        if has_key_parties:
            score += 10.0
            reasons.append("合同主体明确")
        else:
            score -= 5.0
            reasons.append("部分合同主体不明确")

        return min(max(score, 0), 100), "，".join(reasons)

    def _has_circular_dependency(self, relationships: Dict[str, List[str]]) -> bool:
        """检查是否存在循环依赖"""
        # 构建依赖图
        graph = {}
        for contract_id, deps in relationships.items():
            graph[contract_id] = []

            # 从依赖描述中提取依赖的合同ID
            for dep_desc in deps:
                # 简单提取：假设描述格式为 "contract_X 依赖 contract_Y 的签署"
                words = dep_desc.split()
                for word in words:
                    if word.startswith("contract_"):
                        graph[contract_id].append(word)

        # DFS 检测环
        visited = set()
        rec_stack = set()

        def has_cycle(node):
            visited.add(node)
            rec_stack.add(node)

            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        for node in graph:
            if node not in visited:
                if has_cycle(node):
                    return True

        return False

    def _generate_comments(self, dimension_scores: List[EvaluationScore], planning_data: Dict) -> str:
        """生成综合评价"""
        comments = []

        # 找出最高和最低分维度
        max_dim = max(dimension_scores, key=lambda d: d.score)
        min_dim = min(dimension_scores, key=lambda d: d.score)

        if max_dim.score >= 80:
            comments.append(f"在{max_dim.dimension.value}方面表现优秀")
        elif max_dim.score >= 60:
            comments.append(f"在{max_dim.dimension.value}方面表现良好")

        if min_dim.score < 50:
            comments.append(f"在{min_dim.dimension.value}方面需要改进")
        elif min_dim.score < 70:
            comments.append(f"在{min_dim.dimension.value}方面有提升空间")

        # 合同数量评价
        contract_count = len(planning_data.get("contracts", []))
        if contract_count <= 1:
            comments.append("建议增加配套合同以完善交易结构")

        return "；".join(comments) if comments else "方案整体合理"

    def _build_system_prompt(self) -> str:
        """构建系统提示词（用于 LLM 评审）"""
        return """你是一个专业的合同规划评审专家。

你的任务是对多个合同规划方案进行评估，选择最优方案。

## 评估维度

### 1. 完整性 (25%)
- 是否覆盖所有必要的合同类型
- 是否包含主协议和配套协议
- 是否涵盖主要法律关系

### 2. 逻辑性 (30%)
- 签署顺序是否合理
- 合同间依赖关系是否清晰
- 优先级设置是否正确

### 3. 风险识别 (25%)
- 是否识别关键风险点
- 风险提示是否具体
- 是否考虑风险隔离

### 4. 可执行性 (20%)
- 规划是否切实可行
- 整体描述是否清晰
- 合同章节预估是否合理

## 输出格式

返回 JSON 格式：
```json
{
  "best_solution": "模型名称",
  "evaluations": [
    {
      "model_name": "模型名称",
      "total_score": 85.5,
      "dimension_scores": {
        "completeness": {"score": 90, "reason": "..."},
        "logic": {"score": 85, "reason": "..."},
        "risk": {"score": 80, "reason": "..."},
        "executability": {"score": 88, "reason": "..."}
      },
      "comments": "综合评价"
    }
  ],
  "recommendation": "选择建议"
}
```
"""


# 单例
_evaluator_instance: Optional[PlanningSolutionEvaluator] = None


def get_solution_evaluator(llm: Optional[ChatOpenAI] = None) -> PlanningSolutionEvaluator:
    """获取方案评审服务单例"""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = PlanningSolutionEvaluator(llm)
    return _evaluator_instance
