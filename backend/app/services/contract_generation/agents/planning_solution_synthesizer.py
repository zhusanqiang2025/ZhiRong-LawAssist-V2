# backend/app/services/contract_generation/agents/planning_solution_synthesizer.py
"""
方案综合融合服务

核心功能：
分析多个模型的规划方案，提取各自的优点，综合生成一个最优方案

与方案评审的区别：
- 方案评审：评估并选择最优方案
- 方案综合融合：分析各方案优缺点，融合生成新方案
"""

import logging
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from dataclasses import dataclass

from .models import ContractPlanning, PlannedContract

logger = logging.getLogger(__name__)


@dataclass
class SynthesisInput:
    """综合融合输入"""
    model_name: str
    model_perspective: str
    planning_data: Dict[str, Any]


@dataclass
class SynthesisAnalysis:
    """综合分析结果"""
    # 各方案分析
    solution_analyses: List[Dict[str, Any]]  # 每个方案的优缺点分析
    # 提取的优点
    extracted_strengths: Dict[str, List[str]]
    # 识别的缺点
    identified_weaknesses: Dict[str, List[str]]
    # 融合策略
    fusion_strategy: str


class PlanningSolutionSynthesizer:
    """
    方案综合融合服务

    分析多个规划方案，提取优点，综合生成最优方案
    """

    def __init__(self, llm: ChatOpenAI):
        """
        初始化综合融合服务

        Args:
            llm: 用于综合分析的 LLM（建议使用强推理模型）
        """
        self.llm = llm
        self.system_prompt = self._build_system_prompt()

    def synthesize(
        self,
        inputs: List[SynthesisInput],
        user_input: str
    ) -> ContractPlanning:
        """
        综合融合多个方案

        Args:
            inputs: 各模型的规划结果
            user_input: 用户原始输入

        Returns:
            ContractPlanning: 综合融合后的最优规划
        """
        logger.info(f"[SolutionSynthesizer] 开始综合融合 {len(inputs)} 个方案")

        # 步骤1：分析各方案的优缺点
        analysis = self._analyze_solutions(inputs, user_input)

        logger.info(f"[SolutionSynthesizer] 分析完成，融合策略: {analysis.fusion_strategy[:100]}...")

        # 步骤2：基于分析，综合生成最优方案
        final_planning = self._synthesize_fusion(inputs, analysis, user_input)

        logger.info(f"[SolutionSynthesizer] 综合融合完成，生成 {len(final_planning.contracts)} 份合同")

        return final_planning

    def _analyze_solutions(
        self,
        inputs: List[SynthesisInput],
        user_input: str
    ) -> SynthesisAnalysis:
        """
        分析各方案的优缺点

        Args:
            inputs: 各模型的规划结果
            user_input: 用户输入

        Returns:
            SynthesisAnalysis: 综合分析结果
        """
        # 构建分析提示词
        prompt = self._build_analysis_prompt(inputs, user_input)

        try:
            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            content = response.content.strip()

            # 解析分析结果
            return self._parse_analysis(content, inputs)

        except Exception as e:
            logger.error(f"[SolutionSynthesizer] 分析失败: {e}", exc_info=True)
            # 返回默认分析
            return self._get_default_analysis(inputs)

    def _synthesize_fusion(
        self,
        inputs: List[SynthesisInput],
        analysis: SynthesisAnalysis,
        user_input: str
    ) -> ContractPlanning:
        """
        基于分析结果，综合生成融合方案

        Args:
            inputs: 各模型的规划结果
            analysis: 综合分析结果
            user_input: 用户输入

        Returns:
            ContractPlanning: 综合融合后的规划
        """
        # 构建融合生成提示词
        prompt = self._build_fusion_prompt(inputs, analysis, user_input)

        try:
            response = self.llm.invoke([
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=prompt)
            ])

            content = response.content.strip()

            # 解析融合结果
            planning_data = self._parse_planning_result(content)

            # 转换为 ContractPlanning 对象
            return self._to_contract_planning(planning_data)

        except Exception as e:
            logger.error(f"[SolutionSynthesizer] 融合生成失败: {e}", exc_info=True)
            # 降级：返回第一个方案
            return self._to_contract_planning(inputs[0].planning_data)

    def _build_system_prompt(self) -> str:
        """构建系统提示词"""
        return """你是一个专业的交易结构设计专家，擅长分析和综合多个合同规划方案。

你的核心能力是：
1. **深度分析**：准确识别每个方案的优点和缺点
2. **提取精华**：从各方案中提取最有价值的元素
3. **融合创新**：将多个方案的优点融合，生成更优的综合方案

## 分析框架

### 评估维度
1. **完整性**：合同覆盖是否全面，是否有遗漏
2. **逻辑性**：签署顺序、依赖关系是否合理
3. **风险识别**：是否充分识别并规避风险
4. **可执行性**：规划是否切实可行

### 专业视角分析
- **法律风险视角**（Qwen3）：关注风险隔离、法律关系完整性
- **商业逻辑视角**（DeepSeek）：关注交易流程、实际可操作性
- **合规性视角**（GPT-OSS）：关注法律依据、监管要求、标准合同组合

## 融合原则

1. **取长补短**：从每个方案中提取其最优秀的部分
2. **风险优先**：优先采用风险控制更严格的方案
3. **务实平衡**：在理想和现实之间找到最佳平衡点
4. **用户导向**：确保最终方案符合用户的具体需求

## 输出要求

- 只输出 JSON，不要其他说明
- 确保融合后的方案逻辑自洽
- 详细说明融合的依据和理由
"""

    def _build_analysis_prompt(
        self,
        inputs: List[SynthesisInput],
        user_input: str
    ) -> str:
        """构建分析提示词"""
        prompt = f"""## 用户需求

{user_input}

## 各模型规划方案

"""

        # 添加各方案
        for idx, inp in enumerate(inputs, 1):
            prompt += f"""### 方案 {idx}: {inp.model_name} ({inp.model_perspective})

```json
{self._format_planning_data(inp.planning_data)}
```

"""

        prompt += """
## 分析要求

请对以上方案进行深度分析，按照以下 JSON 格式输出：

```json
{
  "solution_analyses": [
    {
      "model_name": "模型名称",
      "model_perspective": "专业视角",
      "strengths": ["优点1", "优点2", "优点3"],
      "weaknesses": ["缺点1", "缺点2"],
      "unique_contributions": ["独特贡献1", "独特贡献2"],
      "overall_assessment": "总体评价"
    }
  ],
  "extracted_strengths": {
    "completeness": ["从哪个方案提取了完整性的优点", "具体内容"],
    "logic": ["从哪个方案提取了逻辑性的优点", "具体内容"],
    "risk_identification": ["从哪个方案提取了风险识别的优点", "具体内容"],
    "executability": ["从哪个方案提取了可执行性的优点", "具体内容"]
  },
  "identified_weaknesses": {
    "missing_contracts": ["缺失的合同", "建议从哪个方案补充"],
    "logic_issues": ["逻辑问题", "建议如何修正"],
    "risk_gaps": ["风险漏洞", "建议如何防范"],
    "execution_barriers": ["执行障碍", "建议如何克服"]
  },
  "fusion_strategy": "详细说明如何融合各方案，包括：1)合同清单如何确定；2)签署顺序如何安排；3)风险点如何防范；4)各方案的具体贡献是什么",
  "recommended_fusion": {
    "contracts_description": "描述最终应该包含哪些合同及其理由",
    "signing_order_description": "描述签署顺序的设计逻辑",
    "risk_notes_description": "描述需要特别关注的风险点"
  }
}
```

请直接输出 JSON，不要使用 markdown 代码块。
"""
        return prompt

    def _build_fusion_prompt(
        self,
        inputs: List[SynthesisInput],
        analysis: SynthesisAnalysis,
        user_input: str
    ) -> str:
        """构建融合生成提示词"""
        prompt = f"""## 用户需求

{user_input}

## 综合分析结果

### 融合策略
{analysis.fusion_strategy}

### 各方案优缺点分析

"""

        # 添加方案分析
        for sol_analysis in analysis.solution_analyses:
            prompt += f"""
**{sol_analysis['model_name']} ({sol_analysis['model_perspective']})**
- 优点：{', '.join(sol_analysis['strengths'])}
- 缺点：{', '.join(sol_analysis['weaknesses'])}
- 独特贡献：{', '.join(sol_analysis['unique_contributions'])}
- 总体评价：{sol_analysis['overall_assessment']}
"""

        # 添加提取的优点
        prompt += "\n### 提取的优点\n\n"
        for dimension, items in analysis.extracted_strengths.items():
            prompt += f"**{dimension}**:\n"
            for item in items:
                prompt += f"  - {item}\n"

        # 添加识别的缺点
        if analysis.identified_weaknesses:
            prompt += "\n### 需要改进的方面\n\n"
            for category, items in analysis.identified_weaknesses.items():
                if items:
                    prompt += f"**{category}**:\n"
                    for item in items:
                        prompt += f"  - {item}\n"

        prompt += """
## 融合生成要求

基于以上分析，请生成一个**综合融合的最优合同规划方案**，要求：

1. **融合各方案优点**：确保每个方案的核心优势都被体现
2. **规避已知缺点**：避免各方案中识别出的问题
3. **逻辑自洽**：确保最终方案内部逻辑一致、合理
4. **符合用户需求**：紧密结合用户的具体交易场景

严格按照以下 JSON 格式输出：

```json
{
  "contracts": [
    {
      "id": "contract_1",
      "title": "合同标题",
      "contract_type": "合同类型",
      "purpose": "该合同在整体交易中的目的和作用（说明融合了哪个方案的优点）",
      "key_parties": ["甲方", "乙方"],
      "priority": 1,
      "dependencies": [],
      "estimated_sections": ["标的条款", "价款条款", "履行条款"],
      "source": "说明该合同主要参考了哪个方案，以及做了哪些改进"
    }
  ],
  "signing_order": ["contract_1", "contract_2", "contract_3"],
  "relationships": {
    "contract_1": ["contract_2 依赖 contract_1 的签署"],
    "contract_2": ["contract_3 依赖 contract_2 的签署"]
  },
  "risk_notes": [
    "风险提示1（说明融合了哪个方案的风险识别）",
    "风险提示2"
  ],
  "overall_description": "整体交易结构的说明（详细描述融合思路和各方案的贡献）",
  "total_estimated_contracts": 3,
  "fusion_summary": {
    "primary_sources": ["主要参考了哪些方案"],
    "key_improvements": ["相比各原始方案的关键改进点"],
    "synthesis_rationale": "综合融合的基本原理和逻辑"
  }
}
```

请直接输出 JSON，不要使用 markdown 代码块。
"""
        return prompt

    def _parse_analysis(self, content: str, inputs: List[SynthesisInput]) -> SynthesisAnalysis:
        """解析分析结果"""
        import json
        import re

        try:
            # 尝试直接解析 JSON
            data = json.loads(content)

            solution_analyses = data.get("solution_analyses", [])
            extracted_strengths = data.get("extracted_strengths", {})
            identified_weaknesses = data.get("identified_weaknesses", {})
            fusion_strategy = data.get("fusion_strategy", "")

            return SynthesisAnalysis(
                solution_analyses=solution_analyses,
                extracted_strengths=extracted_strengths,
                identified_weaknesses=identified_weaknesses,
                fusion_strategy=fusion_strategy
            )

        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            json_match = re.search(r'```json\s*(.+?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group(1))
                    return SynthesisAnalysis(
                        solution_analyses=data.get("solution_analyses", []),
                        extracted_strengths=data.get("extracted_strengths", {}),
                        identified_weaknesses=data.get("identified_weaknesses", {}),
                        fusion_strategy=data.get("fusion_strategy", "")
                    )
                except json.JSONDecodeError:
                    pass

            logger.warning("[SolutionSynthesizer] 解析分析结果失败，使用默认分析")
            return self._get_default_analysis(inputs)

    def _parse_planning_result(self, content: str) -> Dict[str, Any]:
        """解析规划结果"""
        import json
        import re

        try:
            # 尝试直接解析 JSON
            return json.loads(content)

        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            json_match = re.search(r'```json\s*(.+?)\s*```', content, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # 尝试提取花括号内容
            brace_match = re.search(r'\{.+?\}', content, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.warning("[SolutionSynthesizer] 解析规划结果失败")
            return {}

    def _to_contract_planning(self, data: Dict[str, Any]) -> ContractPlanning:
        """转换为 ContractPlanning 对象"""
        contracts = [
            PlannedContract(**contract_data)
            for contract_data in data.get("contracts", [])
        ]

        return ContractPlanning(
            contracts=contracts,
            signing_order=data.get("signing_order", []),
            relationships=data.get("relationships", {}),
            risk_notes=data.get("risk_notes", []),
            overall_description=data.get("overall_description", ""),
            total_estimated_contracts=data.get("total_estimated_contracts", len(contracts))
        )

    def _format_planning_data(self, data: Dict[str, Any]) -> str:
        """格式化规划数据为 JSON 字符串"""
        import json
        return json.dumps(data, ensure_ascii=False, indent=2)

    def _get_default_analysis(self, inputs: List[SynthesisInput]) -> SynthesisAnalysis:
        """获取默认分析（当分析失败时）"""
        solution_analyses = []
        for inp in inputs:
            solution_analyses.append({
                "model_name": inp.model_name,
                "model_perspective": inp.model_perspective,
                "strengths": ["提供了规划方案"],
                "weaknesses": ["分析未完成"],
                "unique_contributions": ["原始方案"],
                "overall_assessment": "因分析失败，保留原始方案"
            })

        return SynthesisAnalysis(
            solution_analyses=solution_analyses,
            extracted_strengths={},
            identified_weaknesses={},
            fusion_strategy="分析失败，直接使用第一个方案"
        )


# 单例
_synthesizer_instance: Optional[PlanningSolutionSynthesizer] = None


def get_solution_synthesizer(llm: Optional[ChatOpenAI] = None) -> PlanningSolutionSynthesizer:
    """获取方案综合融合服务单例"""
    global _synthesizer_instance
    if _synthesizer_instance is None:
        if llm is None:
            # 默认使用 Qwen3-Thinking 作为综合分析模型
            from app.core.llm_config import get_qwen3_llm
            llm = get_qwen3_llm()
        _synthesizer_instance = PlanningSolutionSynthesizer(llm)
    return _synthesizer_instance
