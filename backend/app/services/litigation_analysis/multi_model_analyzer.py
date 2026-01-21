# backend/app/services/litigation_analysis/multi_model_analyzer.py
"""
案件分析 - 多模型智能推演引擎 (Multi-Model Analyzer)

核心职责：
1. 综合输入：整合案情事实、数据库规则、证据分析结论。
2. 场景模拟：根据不同诉讼阶段（起诉/应诉/上诉），切换 LLM 的角色设定。
3. 双模式运行：
   - 单模型模式 (Single): 快速响应，默认使用 Qwen3-235B (性能最强)。
   - 多模型模式 (Multi): 并行调用 Qwen3, DeepSeek, GPT-OSS，通过投票/择优算法输出最稳健的结论。
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== 1. 数据模型定义 ====================

class ScenarioAnalysisResult(BaseModel):
    """
    LLM 输出的标准结构化结果
    """
    summary: str = Field(..., description="案件核心摘要（300字以内）")
    key_facts: List[str] = Field(..., description="经认定的关键法律事实列表")
    
    # 动态字段：起诉时为请求权，应诉时为抗辩点
    legal_arguments: List[str] = Field(..., description="核心法律主张或抗辩事由")
    
    # 规则应用：必须显式引用数据库规则
    rule_application: List[str] = Field(..., description="数据库规则的具体适用分析")
    
    # SWOT 分析
    favorable_factors: List[str] = Field(..., description="有利因素 (Strengths)")
    unfavorable_factors: List[str] = Field(..., description="不利因素/风险点 (Weaknesses/Risks)")
    
    # 结论
    win_rate_prediction: float = Field(..., description="预估胜诉/抗辩成功概率 (0.0-1.0)")
    conclusion: str = Field(..., description="最终结论性法律意见")
    
    confidence: float = Field(..., description="模型自我评估的置信度 (0.0-1.0)")


@dataclass
class ModelResponse:
    """内部封装：单个模型的执行结果"""
    model_name: str
    data: Optional[ScenarioAnalysisResult]
    error: Optional[str] = None
    raw_data: Optional[str] = None  # 新增：保存原始响应用于调试


# ==================== 2. 分析器实现 ====================

class MultiModelAnalyzer:
    """
    智能推演引擎
    适配环境配置：Qwen3-235B, DeepSeek, GPT-OSS-120B
    """

    def __init__(self, mode: str = "multi", selected_model: Optional[str] = None):
        """
        初始化分析器
        Args:
            mode: "single" 或 "multi"
            selected_model: 单模型模式下指定的模型名称 ("qwen", "deepseek", "gpt_oss")
        """
        self.mode = mode
        self.selected_model = selected_model
        
        # 初始化模型池 (基于 .env 配置)
        self.models_pool = self._initialize_models_pool()
        
        # 验证单模型配置
        if mode == "single":
            if not selected_model:
                # 默认首选 Qwen3 (性能最强)，其次 DeepSeek
                if "qwen" in self.models_pool:
                    self.selected_model = "qwen"
                elif "deepseek" in self.models_pool:
                    self.selected_model = "deepseek"
                else:
                    self.selected_model = list(self.models_pool.keys())[0] if self.models_pool else "unknown"
                logger.info(f"[Analyzer] 单模型默认选择: {self.selected_model}")
            elif selected_model not in self.models_pool:
                raise ValueError(f"指定的模型 {selected_model} 不可用。可用模型: {list(self.models_pool.keys())}")

    def _initialize_models_pool(self) -> Dict[str, ChatOpenAI]:
        """根据环境变量初始化所有可用模型"""
        models = {}
        
        # 1. Qwen3-235B-Thinking (主力模型)
        # 对应配置: QWEN3_THINKING_...
        if getattr(settings, "QWEN3_THINKING_ENABLED", False) and settings.QWEN3_THINKING_API_KEY:
            try:
                models["qwen"] = ChatOpenAI(
                    model=settings.QWEN3_THINKING_MODEL,
                    api_key=settings.QWEN3_THINKING_API_KEY,
                    base_url=settings.QWEN3_THINKING_API_URL,
                    temperature=0.1, # 法律分析需要严谨
                    max_tokens=4000,
                    timeout=settings.QWEN3_THINKING_TIMEOUT
                )
                logger.info("[Analyzer] Qwen3-235B (主力) 模型加载成功")
            except Exception as e:
                logger.warning(f"Qwen3 加载失败: {e}")

        # 2. DeepSeek-R1 (逻辑推理)
        # 注意：此配置实际指向火山引擎的 Qwen 模型
        if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_URL:
            try:
                # 直接使用配置中的模型名称，不要强制覆盖
                model_name = getattr(settings, "DEEPSEEK_MODEL", "Qwen3-235B-A22B-Thinking-2507")

                models["deepseek"] = ChatOpenAI(
                    model=model_name,
                    api_key=settings.DEEPSEEK_API_KEY,
                    base_url=settings.DEEPSEEK_API_URL,
                    temperature=0.2,
                    max_tokens=8000
                )
                logger.info(f"[Analyzer] DeepSeek 模型加载成功 | 实际模型: {model_name}")
            except Exception as e:
                logger.warning(f"DeepSeek 加载失败: {e}")

        # 3. GPT-OSS-120B (开源大模型)
        # 对应配置: GPT_OSS_120B_...
        if getattr(settings, "GPT_OSS_120B_API_URL", None):
            try:
                # 注意：本地部署通常不需要 Key，或者 Key 随意
                api_key = getattr(settings, "GPT_OSS_120B_API_KEY", "no-key")
                if not api_key: api_key = "no-key"
                
                models["gpt_oss"] = ChatOpenAI(
                    model=getattr(settings, "GPT_OSS_120B_MODEL", "gpt-oss:120b"),
                    api_key=api_key,
                    base_url=settings.GPT_OSS_120B_API_URL,
                    temperature=0.3
                )
                logger.info("[Analyzer] GPT-OSS-120B 模型加载成功")
            except Exception as e:
                logger.warning(f"GPT-OSS 加载失败: {e}")

        if not models:
            logger.error("未找到任何可用的模型配置！请检查环境变量。")
        
        return models

    async def analyze_parallel(
        self,
        context: str,
        rules: List[str],
        session_id: str,
        case_type: str,
        case_position: str,
        evidence_analysis: Dict[str, Any] = None,
        scenario: str = "pre_litigation"
    ) -> Dict[str, Any]:
        """
        执行分析的主入口
        """
        if not self.models_pool:
            return {"error": "服务配置错误：无可用模型", "status": "failed"}

        logger.info(f"[{session_id}] 开始分析 | 模式: {self.mode} | 场景: {scenario}")
        logger.info(f"[{session_id}] 输入参数: context长度={len(context)}, rules数={len(rules)}")

        # 1. 构建 Prompt
        system_prompt = self._build_system_prompt(scenario, case_position)
        user_prompt = self._build_user_prompt(context, rules, evidence_analysis, scenario)

        # 2. 分发任务
        if self.mode == "single":
            # === 单模型模式 (默认 Qwen3) ===
            model_instance = self.models_pool[self.selected_model]
            result = await self._call_single_model(
                self.selected_model, model_instance, system_prompt, user_prompt
            )

            if result.error:
                logger.error(f"[{session_id}] 分析失败: {result.error}")
                return {
                    "error": f"模型 {self.selected_model} 分析失败: {result.error}",
                    "status": "failed",
                    "mode": "single",
                    "selected_model": self.selected_model
                }

            output = self._format_final_output(result.data, model_name=self.selected_model, mode="single")
            logger.info(f"[{session_id}] 分析成功 | facts数={len(output.get('final_facts', []))}")
            return output

        else:
            # === 多模型模式 (Qwen3 + DeepSeek + GPT-OSS) ===
            tasks = []
            for name, model_instance in self.models_pool.items():
                tasks.append(self._call_single_model(name, model_instance, system_prompt, user_prompt))

            results = await asyncio.gather(*tasks)
            output = self._synthesize_multi_results(results)

            if "error" in output:
                logger.error(f"[{session_id}] 分析失败: {output['error']}")
            else:
                logger.info(f"[{session_id}] 分析成功 | facts数={len(output.get('final_facts', []))}")

            return output

    async def _call_single_model(
        self,
        name: str,
        model: ChatOpenAI,
        sys_prompt: str,
        user_prompt: str
    ) -> ModelResponse:
        """调用单个模型（原始生成 + 强力清洗模式）"""
        logger.info(f"[{name}] 模型开始执行 | context长度: {len(user_prompt)}")

        # 1. 强制使用原始调用 (不使用 structured_output)
        try:
            import re

            # 提示 LLM 返回 JSON，但不依赖框架校验
            sys_prompt += "\n\n请务必只返回纯 JSON 格式，不要包含 Markdown 标记，不要包含其他解释。"

            response = await model.ainvoke([
                SystemMessage(content=sys_prompt),
                HumanMessage(content=user_prompt)
            ])

            raw_text = response.content
            logger.info(f"[{name}] 原始响应预览(前500字): {raw_text[:500]}...")

            # 2. 强力清洗 (核心修复)
            # 尝试提取 ```json ... ```
            json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
            if json_match:
                clean_text = json_match.group(1)
                logger.info(f"[{name}] 从 ```json 代码块提取成功")
            else:
                # 尝试提取第一个 { 到最后一个 }
                json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                clean_text = json_match.group(0) if json_match else raw_text
                logger.info(f"[{name}] 从原始文本提取 JSON")

            # 3. 解析与对象构建
            try:
                data_dict = json.loads(clean_text)

                # 手动构建 Pydantic 对象 (容错处理)
                result_obj = ScenarioAnalysisResult(
                    summary=data_dict.get("summary", "分析完成"),
                    key_facts=data_dict.get("key_facts", []),
                    legal_arguments=data_dict.get("legal_arguments", []),
                    rule_application=data_dict.get("rule_application", []),
                    favorable_factors=data_dict.get("favorable_factors", []),
                    unfavorable_factors=data_dict.get("unfavorable_factors", []),
                    win_rate_prediction=float(data_dict.get("win_rate_prediction", 0.5)),
                    conclusion=data_dict.get("conclusion", "无详细结论"),
                    confidence=float(data_dict.get("confidence", 0.8))
                )

                logger.info(f"[{name}] 解析成功，生成有效结果 | 置信度: {result_obj.confidence}")
                return ModelResponse(model_name=name, data=result_obj)

            except json.JSONDecodeError as je:
                logger.error(f"[{name}] JSON解析失败: {je}")
                logger.error(f"[{name}] 清洗后的文本(前500字): {clean_text[:500]}...")
                # 即使 JSON 失败，也尝试把原始文本塞进去，不要丢弃
                fallback_obj = ScenarioAnalysisResult(
                    summary="格式解析失败，请查看原始数据",
                    key_facts=[],
                    legal_arguments=[],
                    rule_application=[],
                    favorable_factors=[],
                    unfavorable_factors=["JSON格式解析失败"],
                    win_rate_prediction=0.5,
                    conclusion=raw_text[:2000],  # 把原始分析结果放这里
                    confidence=0.1
                )
                return ModelResponse(model_name=name, data=fallback_obj, raw_data=raw_text)

        except Exception as e:
            logger.error(f"[{name}] 模型调用异常: {e}")
            import traceback
            logger.error(f"[{name}] 异常堆栈: {traceback.format_exc()}")
            # 返回降级对象
            return ModelResponse(model_name=name, error=str(e), data=self._get_fallback_data())

    def _get_fallback_data(self) -> ScenarioAnalysisResult:
        """返回降级数据对象"""
        return ScenarioAnalysisResult(
            summary="模型分析失败，基于规则生成基础结论",
            key_facts=["由于技术限制无法自动提取关键事实，请人工审查原文"],
            legal_arguments=["建议咨询专业律师进行详细分析"],
            rule_application=[],
            favorable_factors=["需要人工审查"],
            unfavorable_factors=["模型分析失败"],
            win_rate_prediction=0.5,
            conclusion="建议人工审查案件材料后进行专业法律咨询",
            confidence=0.1
        )

    def _synthesize_multi_results(self, results: List[ModelResponse]) -> Dict[str, Any]:
        """多模型结果聚合"""
        valid_results = [r for r in results if r.data is not None]

        if not valid_results:
            return {
                "error": "所有模型分析均失败",
                "status": "failed",
                "mode": "multi",
                "selected_model": None
            }

        # 策略：在 Qwen3 和 DeepSeek 中优先选择置信度高的
        # 如果 Qwen3 成功且置信度不错 (>0.8)，优先用 Qwen3 (因为它是主力)
        best_result = None

        # 查找 Qwen 结果
        qwen_res = next((r for r in valid_results if r.model_name == "qwen"), None)

        if qwen_res and qwen_res.data.confidence >= 0.8:
            best_result = qwen_res
        else:
            # 否则取最高置信度
            best_result = max(valid_results, key=lambda x: x.data.confidence)

        # 添加安全检查
        if best_result is None or best_result.data is None:
            return {
                "error": "无法选择最佳分析结果",
                "status": "failed",
                "mode": "multi",
                "selected_model": None
            }

        output = self._format_final_output(best_result.data, model_name=best_result.model_name, mode="multi")
        
        # 附加对比数据
        output["model_comparison"] = {
            res.model_name: {
                "win_rate": res.data.win_rate_prediction,
                "confidence": res.data.confidence,
                "fact_count": len(res.data.key_facts)
            } for res in valid_results
        }
        return output

    def _format_final_output(
        self, 
        data: ScenarioAnalysisResult, 
        model_name: str, 
        mode: str
    ) -> Dict[str, Any]:
        """格式化输出"""
        return {
            "status": "success",
            "mode": mode,
            "selected_model": model_name,
            "final_summary": data.summary,
            "final_facts": data.key_facts,
            "final_legal_arguments": data.legal_arguments,
            "rule_application": data.rule_application,
            "final_strengths": data.favorable_factors,
            "final_weaknesses": data.unfavorable_factors,
            "final_strength": data.win_rate_prediction,
            "conclusion": data.conclusion,
            "confidence": data.confidence,
            "raw_data": data.dict()
        }

    def _build_system_prompt(self, scenario: str, position: str) -> str:
        """构建 System Prompt"""
        base_role = "你是一位精通中国法律的资深诉讼律师，拥有20年实务经验。"
        
        if scenario == "pre_litigation":
            return f"{base_role} 当前任务是【诉前评估】。请站在【{position}】的立场，客观评估发起诉讼的可行性。"
        elif scenario == "defense":
            return f"{base_role} 当前任务是【应诉策略】。请站在【被告/应诉人】的立场，寻找原告漏洞，构建抗辩防线。"
        elif scenario == "appeal":
            return f"{base_role} 当前任务是【二审评估】。请模拟【二审法官】思维，审查一审判决错误。"
        elif scenario == "execution":
            return f"{base_role} 当前任务是【执行分析】。重点分析财产线索和执行异议风险。"
        else:
            return f"{base_role} 请进行全面法律分析。"

    def _build_user_prompt(
        self, 
        context: str, 
        rules: List[str], 
        evidence_result: Dict[str, Any], 
        scenario: str
    ) -> str:
        """构建 User Prompt"""
        evidence_summary = "暂无详细证据分析。"
        if evidence_result and "analysis_points" in evidence_result:
            count = len(evidence_result.get("analysis_points", []))
            assessment = evidence_result.get("admissibility_assessment", "未知")
            evidence_summary = f"证据整体评价: {assessment}。发现 {count} 个具体问题。"

        prompt = f"""
请基于以下材料进行法律推演。

【案件材料】
{context}

【审查规则】(必须适用)
{chr(10).join(rules) if rules else "无特殊规则。"}

【证据结论】
{evidence_summary}

【指令】
1. 必须显式引用审查规则。
2. 证据缺口必须影响胜诉率预估。
3. 按 JSON 结构输出。
"""
        return prompt

def get_multi_model_analyzer(mode: str = "multi", selected_model: Optional[str] = None) -> MultiModelAnalyzer:
    return MultiModelAnalyzer(mode=mode, selected_model=selected_model)