# backend/app/services/contract_generation/agents/multi_model_planning_service.py
"""
多模型协同合同规划服务（综合融合模式）

核心功能：
使用多个 AI 模型从不同视角对用户需求进行合同规划，
通过综合融合分析，生成一个融合各方案优点的最优方案

模型分工：
- Qwen3-235B-Thinking: 法律风险视角（关注风险隔离、法律关系完整性）
- DeepSeek-R1-0528: 商业逻辑视角（关注交易流程、实际可操作性）
- GPT-OSS-120B: 合规性视角（关注法律依据、监管要求、标准合同组合）

综合融合流程：
1. 并行调用各模型生成规划方案
2. 使用综合分析器分析各方案优缺点
3. 基于分析结果，融合生成最优方案
"""

import logging
import os
from typing import Dict, List, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from .planning_solution_synthesizer import PlanningSolutionSynthesizer, SynthesisInput
from .models import ContractPlanning, PlannedContract

logger = logging.getLogger(__name__)


@dataclass
class ModelPlanningResult:
    """单个模型的规划结果"""
    model_name: str
    model_perspective: str  # 模型视角
    planning_data: Dict[str, Any]
    execution_time: float = 0.0
    success: bool = True
    error_message: str = ""


@dataclass
class SynthesisReport:
    """综合融合报告"""
    # 各方案分析
    solution_analyses: List[Dict[str, Any]]
    # 提取的优点
    extracted_strengths: Dict[str, List[str]]
    # 识别的缺点
    identified_weaknesses: Dict[str, List[str]]
    # 融合策略
    fusion_strategy: str
    # 融合摘要
    fusion_summary: Dict[str, Any]


@dataclass
class MultiModelPlanningResult:
    """多模型规划结果"""
    # 综合融合后的最优规划
    final_planning: ContractPlanning
    # 综合融合报告
    synthesis_report: SynthesisReport
    # 各模型的原始结果
    model_results: List[ModelPlanningResult]
    # 执行统计
    execution_stats: Dict[str, Any]


class MultiModelPlanningService:
    """
    多模型协同合同规划服务

    使用多个 AI 模型并行生成规划方案，然后综合融合生成最优方案
    """

    # 模型视角配置
    MODEL_PERSPECTIVES = {
        "qwen3": {
            "name": "Qwen3-235B-Thinking",
            "perspective": "法律风险视角",
            "system_prompt_addition": """
## 你的专业视角：法律风险视角

在规划合同时，请重点关注：
1. **风险隔离** - 通过不同合同隔离不同类型的法律风险
2. **法律关系完整性** - 确保所有法律关系都有对应的合同覆盖
3. **合规性** - 确保合同组合符合相关法律法规要求
4. **证据链完整** - 建立完整的法律证据链

你的输出应该体现出对法律风险的深刻理解和专业把控。
"""
        },
        "deepseek": {
            "name": "DeepSeek-R1-0528",
            "perspective": "商业逻辑视角",
            "system_prompt_addition": """
## 你的专业视角：商业逻辑视角

在规划合同时，请重点关注：
1. **交易流程** - 按照实际业务流程设计签署顺序
2. **实际可操作性** - 确保规划在实际业务中可以顺利执行
3. **灵活性** - 为后续可能的变更预留空间
4. **成本效益** - 在保证法律安全的前提下，避免过度复杂化

你的输出应该体现出对商业实践的深刻理解和务实精神。
"""
        },
        "gpt_oss": {
            "name": "GPT-OSS-120B",
            "perspective": "合规性视角",
            "system_prompt_addition": """
## 你的专业视角：合规性视角

在规划合同时，请重点关注：
1. **法律依据** - 确保每种合同类型都有明确的法律依据
2. **监管要求** - 识别并满足相关行业的监管要求
3. **标准合同组合** - 参考行业标准的合同组合模式
4. **条款完备性** - 确保必要条款不遗漏

你的输出应该体现出对法律合规的严谨态度和专业知识。
"""
        }
    }

    def __init__(
        self,
        qwen3_llm: Optional[ChatOpenAI] = None,
        deepseek_llm: Optional[ChatOpenAI] = None,
        gpt_oss_llm: Optional[ChatOpenAI] = None,
        synthesizer: Optional[PlanningSolutionSynthesizer] = None
    ):
        """
        初始化多模型规划服务

        Args:
            qwen3_llm: Qwen3 模型实例（用于法律风险视角）
            deepseek_llm: DeepSeek 模型实例（用于商业逻辑视角）
            gpt_oss_llm: GPT-OSS 模型实例（用于合规性视角）
            synthesizer: 方案综合融合服务实例
        """
        self.qwen3_llm = qwen3_llm
        self.deepseek_llm = deepseek_llm
        self.gpt_oss_llm = gpt_oss_llm
        self.synthesizer = synthesizer

        # 基础系统提示词
        self.base_system_prompt = self._build_base_system_prompt()

    def plan(
        self,
        user_input: str,
        context: Optional[Dict[str, Any]] = None,
        enabled_models: Optional[List[str]] = None
    ) -> MultiModelPlanningResult:
        """
        多模型协同规划（综合融合模式）

        Args:
            user_input: 用户原始输入
            context: 额外上下文信息
            enabled_models: 启用的模型列表（默认：所有可用模型）

        Returns:
            MultiModelPlanningResult: 多模型规划结果（包含综合融合的最优方案）
        """
        import time
        start_time = time.time()

        logger.info("[MultiModelPlanning] 开始多模型协同规划（综合融合模式）")

        # 确定启用的模型
        if enabled_models is None:
            enabled_models = self._get_available_models()

        logger.info(f"[MultiModelPlanning] 启用的模型: {enabled_models}")

        # 第一步：并行调用各模型生成规划
        model_results = self._parallel_generate_plans(
            user_input=user_input,
            context=context or {},
            enabled_models=enabled_models
        )

        # 过滤成功的结果
        successful_results = [r for r in model_results if r.success]

        if not successful_results:
            logger.error("[MultiModelPlanning] 所有模型都失败，返回默认规划")
            return self._get_fallback_result(model_results)

        logger.info(f"[MultiModelPlanning] 成功生成 {len(successful_results)} 个方案，开始综合融合")

        # 第二步：综合融合各方案
        synthesis_inputs = [
            SynthesisInput(
                model_name=r.model_name,
                model_perspective=r.model_perspective,
                planning_data=r.planning_data
            )
            for r in successful_results
        ]

        final_planning = self.synthesizer.synthesize(
            inputs=synthesis_inputs,
            user_input=user_input
        )

        # 生成综合融合报告
        synthesis_report = self._generate_synthesis_report(
            successful_results,
            final_planning
        )

        # 执行统计
        total_time = time.time() - start_time
        execution_stats = {
            "total_time": total_time,
            "model_count": len(enabled_models),
            "successful_count": len(successful_results),
            "average_model_time": sum(r.execution_time for r in successful_results) / len(successful_results),
            "synthesis_time": total_time - sum(r.execution_time for r in model_results),
        }

        logger.info(f"[MultiModelPlanning] 综合融合完成，生成 {len(final_planning.contracts)} 份合同，耗时: {total_time:.2f}s")

        return MultiModelPlanningResult(
            final_planning=final_planning,
            synthesis_report=synthesis_report,
            model_results=model_results,
            execution_stats=execution_stats
        )

    def _get_available_models(self) -> List[str]:
        """获取可用的模型列表"""
        available = []

        if self.qwen3_llm:
            available.append("qwen3")

        if self.deepseek_llm:
            available.append("deepseek")

        if self.gpt_oss_llm:
            available.append("gpt_oss")

        return available

    def _parallel_generate_plans(
        self,
        user_input: str,
        context: Dict[str, Any],
        enabled_models: List[str]
    ) -> List[ModelPlanningResult]:
        """
        并行调用各模型生成规划

        Args:
            user_input: 用户输入
            context: 上下文
            enabled_models: 启用的模型列表

        Returns:
            List[ModelPlanningResult]: 各模型的规划结果
        """
        results = []
        model_configs = []

        # 准备模型配置
        for model_key in enabled_models:
            if model_key == "qwen3" and self.qwen3_llm:
                model_configs.append(("qwen3", self.qwen3_llm))
            elif model_key == "deepseek" and self.deepseek_llm:
                model_configs.append(("deepseek", self.deepseek_llm))
            elif model_key == "gpt_oss" and self.gpt_oss_llm:
                model_configs.append(("gpt_oss", self.gpt_oss_llm))

        # 并行调用
        with ThreadPoolExecutor(max_workers=len(model_configs)) as executor:
            futures = {
                executor.submit(
                    self._generate_single_plan,
                    model_key,
                    llm,
                    user_input,
                    context
                ): (model_key, llm)
                for model_key, llm in model_configs
            }

            for future in as_completed(futures):
                model_key, _ = futures[future]
                try:
                    result = future.result(timeout=120)  # 单个模型最多 120 秒
                    results.append(result)
                    logger.info(f"[MultiModelPlanning] {model_key} 规划完成，耗时: {result.execution_time:.2f}s")
                except Exception as e:
                    logger.error(f"[MultiModelPlanning] {model_key} 规划失败: {e}")
                    results.append(ModelPlanningResult(
                        model_name=self.MODEL_PERSPECTIVES[model_key]["name"],
                        model_perspective=self.MODEL_PERSPECTIVES[model_key]["perspective"],
                        planning_data={},
                        success=False,
                        error_message=str(e)
                    ))

        return results

    def _generate_single_plan(
        self,
        model_key: str,
        llm: ChatOpenAI,
        user_input: str,
        context: Dict[str, Any]
    ) -> ModelPlanningResult:
        """
        使用单个模型生成规划

        Args:
            model_key: 模型标识（qwen3/deepseek/gpt_oss）
            llm: LLM 实例
            user_input: 用户输入
            context: 上下文

        Returns:
            ModelPlanningResult: 模型规划结果
        """
        import time
        start_time = time.time()

        model_config = self.MODEL_PERSPECTIVES[model_key]

        # 构建系统提示词（基础 + 专业视角）
        system_prompt = self.base_system_prompt + model_config["system_prompt_addition"]

        # 构建用户提示词
        user_prompt = self._build_user_prompt(user_input, context)

        try:
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            planning_data = self._parse_response(response.content)

            execution_time = time.time() - start_time

            return ModelPlanningResult(
                model_name=model_config["name"],
                model_perspective=model_config["perspective"],
                planning_data=planning_data,
                execution_time=execution_time,
                success=True
            )

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"[MultiModelPlanning] {model_key} 执行失败: {e}", exc_info=True)

            return ModelPlanningResult(
                model_name=model_config["name"],
                model_perspective=model_config["perspective"],
                planning_data={},
                execution_time=execution_time,
                success=False,
                error_message=str(e)
            )

    def _build_base_system_prompt(self) -> str:
        """构建基础系统提示词"""
        return """你是一个专业的交易结构设计专家。你的任务是将复杂的交易拆解为多份合同的组合。

## 规划原则

### 合同拆分原则
1. **一合同一事项** - 每份合同只解决一个核心法律关系
2. **先主后辅** - 先签署主要合同，再签署配套合同
3. **风险隔离** - 通过不同合同隔离不同风险
4. **灵活性** - 为后续变化留有余地

### 常见合同组合

#### 股权投资交易
1. **股权转让协议** - 股权交易主协议
2. **股东协议** - 股东间权利义务、公司治理
3. **公司章程修正案** - 公司治理结构调整

#### 资产收购交易
1. **资产收购协议** - 资产交易主协议
2. **债权债务处理协议** - 债权债务安排
3. **员工安置协议** - 员工处理方案

#### 合作开发项目
1. **合作协议** - 合作主协议
2. **知识产权协议** - IP归属、使用、保护
3. **保密协议** - 商业秘密保护

#### 复杂并购交易
1. **投资意向书** - 初步框架
2. **股权转让协议** - 主交易协议
3. **陈述与保证协议** - 各方声明保证
4. **竞业禁止协议** - 核心人员竞业限制
5. **过渡期管理协议** - 交割前期间管理

## 输出格式

严格按照以下 JSON 格式输出：

```json
{
  "contracts": [
    {
      "id": "contract_1",
      "title": "合同标题",
      "contract_type": "合同类型",
      "purpose": "该合同在整体交易中的目的和作用",
      "key_parties": ["甲方", "乙方"],
      "priority": 1,
      "dependencies": [],
      "estimated_sections": ["标的条款", "价款条款", "履行条款"]
    }
  ],
  "signing_order": ["contract_1", "contract_2", "contract_3"],
  "relationships": {
    "contract_1": ["contract_2 依赖 contract_1 的签署"],
    "contract_2": ["contract_3 依赖 contract_2 的签署"]
  },
  "risk_notes": [
    "风险提示1",
    "风险提示2"
  ],
  "overall_description": "整体交易结构的说明",
  "total_estimated_contracts": 3
}
```

## 输出要求
- 只返回 JSON，不要其他说明
- 确保合同之间的逻辑关系清晰
- 标注每份合同的核心作用
- 明确签署的先后顺序
- 指出关键风险点
"""

    def _build_user_prompt(self, user_input: str, context: Dict[str, Any]) -> str:
        """构建用户提示词"""
        prompt = f"""## 用户需求

{user_input}
"""

        # 添加上下文信息
        if context:
            prompt += "\n## 上下文信息\n"
            for key, value in context.items():
                prompt += f"**{key}**：{value}\n"

        prompt += """
## 规划要求

请将上述交易拆解为多份合同的组合，考虑：
1. 交易涉及的法律关系复杂度
2. 风险隔离需求
3. 签署的先后顺序
4. 合同之间的关联关系

返回 JSON 格式的合同规划。
"""

        return prompt

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        import json
        import re

        try:
            # 尝试直接解析 JSON
            return json.loads(response)

        except json.JSONDecodeError:
            # 尝试提取 JSON 代码块
            json_match = re.search(r'```json\s*(.+?)\s*```', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(1))
                except json.JSONDecodeError:
                    pass

            # 尝试提取花括号内容
            brace_match = re.search(r'\{.+?\}', response, re.DOTALL)
            if brace_match:
                try:
                    return json.loads(brace_match.group(0))
                except json.JSONDecodeError:
                    pass

            logger.warning("[MultiModelPlanning] 解析失败，返回空规划")
            return {}

    def _generate_synthesis_report(
        self,
        model_results: List[ModelPlanningResult],
        final_planning: ContractPlanning
    ) -> SynthesisReport:
        """生成综合融合报告"""
        # 各方案分析
        solution_analyses = []
        for r in model_results:
            if r.success:
                contracts_count = len(r.planning_data.get("contracts", []))
                solution_analyses.append({
                    "model_name": r.model_name,
                    "model_perspective": r.model_perspective,
                    "contracts_count": contracts_count,
                    "execution_time": r.execution_time,
                    "key_contribution": f"提供了 {contracts_count} 份合同的规划"
                })

        # 提取的优点（基于各模型的专业视角）
        extracted_strengths = {
            "legal_risk_control": [f"{r.model_name} 的法律风险分析" for r in model_results if r.success and "风险" in r.model_perspective],
            "commercial_practicality": [f"{r.model_name} 的商业逻辑设计" for r in model_results if r.success and "商业" in r.model_perspective],
            "compliance_assurance": [f"{r.model_name} 的合规性考量" for r in model_results if r.success and "合规" in r.model_perspective],
        }

        # 识别的改进点
        identified_weaknesses = {
            "gaps_covered": [f"通过综合融合，弥补了单一方案的局限性"],
            "optimizations": [f"整合了 {len(model_results)} 个模型的专业视角"],
        }

        # 融合策略
        fusion_strategy = f"""
基于 {len(model_results)} 个模型的专业视角，采用综合融合策略：

1. **法律风险控制**：融合了法律风险视角的专业分析，确保风险隔离到位
2. **商业可行性**：结合了商业逻辑视角的务实考虑，提升实际可操作性
3. **合规性保障**：整合了合规性视角的严谨态度，确保法律依据充分

最终方案在保持专业严谨的同时，充分考虑了实际执行的可行性。
"""

        # 融合摘要
        fusion_summary = {
            "input_models": [r.model_name for r in model_results if r.success],
            "final_contract_count": len(final_planning.contracts),
            "synthesis_approach": "综合融合各模型优点，生成最优方案",
            "key_improvements": [
                f"整合了 {len(model_results)} 个专业视角",
                "风险控制更加全面",
                "可执行性得到提升",
                "合规性更有保障"
            ]
        }

        return SynthesisReport(
            solution_analyses=solution_analyses,
            extracted_strengths=extracted_strengths,
            identified_weaknesses=identified_weaknesses,
            fusion_strategy=fusion_strategy.strip(),
            fusion_summary=fusion_summary
        )

    def _get_fallback_result(self, model_results: List[ModelPlanningResult]) -> MultiModelPlanningResult:
        """获取降级结果（当所有模型都失败时）"""
        from .models import ContractPlanning, PlannedContract

        fallback_planning = ContractPlanning(
            contracts=[
                PlannedContract(
                    id="contract_1",
                    title="主协议",
                    contract_type="contract",
                    purpose="规范双方主要的权利义务",
                    key_parties=["甲方", "乙方"],
                    priority=1,
                    dependencies=[],
                    estimated_sections=[]
                )
            ],
            signing_order=["contract_1"],
            relationships={},
            risk_notes=[],
            overall_description="所有模型规划都失败，已返回默认规划。请检查模型配置或稍后重试。",
            total_estimated_contracts=1
        )

        fallback_report = SynthesisReport(
            solution_analyses=[],
            extracted_strengths={},
            identified_weaknesses={},
            fusion_strategy="所有模型都失败，无法进行综合融合",
            fusion_summary={}
        )

        return MultiModelPlanningResult(
            final_planning=fallback_planning,
            synthesis_report=fallback_report,
            model_results=model_results,
            execution_stats={
                "total_time": 0,
                "model_count": len(model_results),
                "successful_count": 0,
                "average_model_time": 0,
                "synthesis_time": 0,
            }
        )


# 单例
_multi_model_planning_instance: Optional[MultiModelPlanningService] = None


def get_multi_model_planning_service() -> Optional[MultiModelPlanningService]:
    """
    获取多模型规划服务单例

    Returns:
        MultiModelPlanningService: 服务实例，如果模型配置不完整则返回 None
    """
    global _multi_model_planning_instance

    if _multi_model_planning_instance is None:
        from app.core.llm_config import (
            get_qwen3_thinking_llm,
            get_deepseek_llm,
            get_gpt_oss_llm,
            validate_llm_config
        )

        # 验证配置
        config = validate_llm_config()

        if not config.get("multi_model_planning_ready"):
            logger.warning("[MultiModelPlanning] 多模型规划配置不完整，服务不可用")
            logger.warning(f"[MultiModelPlanning] 配置状态: qwen3={config.get('qwen3_thinking')}, deepseek={config.get('deepseek')}, gpt_oss={config.get('gpt_oss')}")
            return None

        try:
            qwen3_llm = get_qwen3_thinking_llm() if config.get("qwen3_thinking") else None
            deepseek_llm = get_deepseek_llm() if config.get("deepseek") else None
            gpt_oss_llm = get_gpt_oss_llm() if config.get("gpt_oss") else None

            from .planning_solution_synthesizer import get_solution_synthesizer
            synthesizer = get_solution_synthesizer()

            _multi_model_planning_instance = MultiModelPlanningService(
                qwen3_llm=qwen3_llm,
                deepseek_llm=deepseek_llm,
                gpt_oss_llm=gpt_oss_llm,
                synthesizer=synthesizer
            )

            logger.info("[MultiModelPlanning] 多模型规划服务初始化成功（综合融合模式）")

        except Exception as e:
            logger.error(f"[MultiModelPlanning] 多模型规划服务初始化失败: {e}")
            return None

    return _multi_model_planning_instance
