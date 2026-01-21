# backend/app/services/risk_analysis/multi_model_analyzer.py

"""
多模型并行分析器 (优化版)

深度集成 Level 2 (增强分析) 和 Level 3 (场景规则) 的成果。
通过注入 "交易全景" 和 "主体画像"，显著提升 LLM 的分析深度。
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from difflib import SequenceMatcher

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from pydantic import BaseModel, Field

from app.core.config import settings
# --- 新增导入：使用统一的 JSON 清洗工具 ---
from app.utils.json_helper import safe_parse_json
# -----------------------------------------

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

@dataclass
class ModelAnalysisResult:
    """单个模型的分析结果"""
    model_name: str
    risk_items: List[Dict[str, Any]]
    summary: str
    risk_distribution: Dict[str, int]
    confidence: float
    raw_response: Optional[str] = None
    error: Optional[str] = None


@dataclass
class ComparisonResult:
    """结果对比"""
    best_model: str
    best_result: ModelAnalysisResult
    comparison_scores: Dict[str, float]
    comparison_reasons: Dict[str, str]


class RiskItemExtraction(BaseModel):
    """LLM 提取的风险项"""
    title: str = Field(..., description="风险点标题")
    description: str = Field(..., description="详细描述")
    risk_level: str = Field(..., description="风险等级：low/medium/high/critical")
    confidence: float = Field(..., ge=0, le=1, description="置信度 0-1")
    reasons: List[str] = Field(default_factory=list, description="理由列表")
    suggestions: List[str] = Field(default_factory=list, description="规避建议列表")


class RiskAnalysisExtraction(BaseModel):
    """LLM 提取的完整分析结果"""
    summary: str = Field(..., description="总体风险摘要")
    risk_items: List[RiskItemExtraction] = Field(default_factory=list, description="风险项列表")
    total_confidence: float = Field(..., ge=0, le=1, description="总体置信度")


# ==================== 多模型分析器 ====================

class MultiModelAnalyzer:
    """
    多模型并行分析器
    """

    def __init__(self):
        self.models = self._initialize_models()
        self.synthesis_model = self._get_synthesis_model()

    def _initialize_models(self) -> Dict[str, ChatOpenAI]:
        """初始化三个分析模型"""
        models = {}

        # 配置参数复用
        common_kwargs = {
            "temperature": 0,
            "request_timeout": 120
        }

        # 1. DeepSeek-R1 - 规则执行者
        if settings.DEEPSEEK_API_KEY and settings.DEEPSEEK_API_URL:
            models["deepseek"] = ChatOpenAI(
                model="deepseek-chat",
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_API_URL,
                max_tokens=8000,
                **common_kwargs
            )
            logger.info("[MultiModelAnalyzer] DeepSeek 初始化成功")

        # 2. GPT-OSS-120B - 结构分析专家
        try:
            from app.core.llm_config import get_gpt_oss_llm
            models["gpt_oss"] = get_gpt_oss_llm()
            logger.info("[MultiModelAnalyzer] GPT-OSS 初始化成功")
        except Exception:
            pass

        # 3. Qwen3-235B-Thinking - 深度分析师
        if settings.LANGCHAIN_API_KEY:
            models["qwen3_235b"] = ChatOpenAI(
                model=settings.MODEL_NAME or "Qwen3-235B-A22B-Thinking-2507",
                api_key=settings.LANGCHAIN_API_KEY,
                base_url=settings.LANGCHAIN_API_BASE_URL,
                max_tokens=16000,
                **common_kwargs
            )
            logger.info("[MultiModelAnalyzer] Qwen3-235B 初始化成功")

        return models

    def _get_synthesis_model(self) -> Optional[ChatOpenAI]:
        try:
            from app.core.llm_config import get_qwen3_thinking_llm
            return get_qwen3_thinking_llm()
        except Exception:
            # 降级使用 qwen3_235b
            return self.models.get("qwen3_235b")

    def _build_system_prompt_for_model(self, model_name: str, enhanced_data: Optional[Dict]) -> str:
        """
        构建动态 System Prompt
        根据增强分析结果 (Enhanced Data) 调整模型人设
        """
        # 提取高层上下文
        contract_status = enhanced_data.get("contract_status", "未知") if enhanced_data else "未知"

        # 基础人设
        base_prompts = {
            "deepseek": "你是'规则执行者'，专注于严格按照给定的法律规则进行条款扫描。宁可错杀，不可漏过。",
            "gpt_oss": "你是'结构分析专家'，专注于评估交易架构的逻辑性、完整性以及条款间的制衡关系。",
            "qwen3_235b": "你是'深度分析师'，擅长通过多步推理发现隐蔽的法律陷阱和商业风险。"
        }
        base = base_prompts.get(model_name, base_prompts["deepseek"])

        # 动态调整
        status_instruction = ""
        if "争议" in contract_status or "诉讼" in contract_status:
            status_instruction = "\n\n【特别警示】当前合同处于【争议/诉讼状态】。请以“模拟法庭辩论”的视角进行分析，重点寻找对我方不利的模糊条款、证据缺失风险及违约责任陷阱。"
        elif "磋商" in contract_status:
            status_instruction = "\n\n【特别警示】当前合同处于【磋商阶段】。请重点关注商业条款的合理性、缔约过失风险及未来退出的灵活性。"

        return f"{base}\n\n## 核心原则\n1. 严格遵循JSON输出格式\n2. 风险描述必须具体到条款{status_instruction}"

    async def analyze_parallel(
            self,
            context: str,
            rules: List[Dict[str, Any]],
            session_id: str,
            analysis_mode: str = "multi",  # 默认多模型
            selected_model: Optional[str] = None,  # 单模型模式下指定的模型名称（如 "deepseek"）
            enhanced_data: Optional[Dict[str, Any]] = None,
            progress_callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        两阶段并行分析流程（支持单/多模型切换）
        Args:
            progress_callback: 进度回调函数 (step: str, progress: float, message: str) -> None
        """

        # 定义进度更新辅助函数
        async def update_progress(step: str, progress: float, message: str):
            if progress_callback:
                await progress_callback(step, progress, message)

        mode_text = "单模型极速" if analysis_mode == "single" else "多模型综合"
        logger.info(f"[MultiModelAnalyzer] 开始分析 ({mode_text}), 增强上下文: {'有' if enhanced_data else '无'}")

        # 阶段1：准备分析上下文 (75-78%)
        await update_progress("prepare_context", 0.76, "正在准备分析上下文...")

        # 1. 构建 Prompt
        base_prompt = self._build_context_aware_prompt(context, rules, enhanced_data)

        # 2. 确定要运行的模型列表
        target_models = self.models
        if analysis_mode == "single":
            if selected_model and selected_model in self.models:
                target_models = {selected_model: self.models[selected_model]}
            else:
                # 默认降级：优先 Qwen，其次 DeepSeek
                default_model = "qwen3_235b" if "qwen3_235b" in self.models else "deepseek"
                if default_model in self.models:
                    target_models = {default_model: self.models[default_model]}
                    logger.info(f"[MultiModelAnalyzer] 单模型模式未指定或指定错误，降级使用: {default_model}")
                else:
                    return {"error": "没有可用的模型"}

        logger.info(f"[MultiModelAnalyzer] 即将运行的模型: {list(target_models.keys())}")

        # 阶段2：执行并行分析 (78-88%)
        analysis_message = "正在执行单模型分析..." if analysis_mode == "single" else "正在执行多模型并行分析..."
        await update_progress("parallel_analysis", 0.78, analysis_message)

        # 3. 第一阶段：执行分析
        # 注意：这里传入 target_models 而不是 self.models
        stage1_results = await self._parallel_analyze_subset(target_models, base_prompt, session_id, enhanced_data)

        successful_results = {k: v for k, v in stage1_results.items() if v.error is None}
        if not successful_results:
            return {"error": "模型分析失败", "stage1_results": {}}

        complete_message = "单模型分析完成" if analysis_mode == "single" else "多模型分析完成"
        await update_progress("parallel_analysis", 0.88, complete_message)

        # ==========================================
        # 分支逻辑：单模型 vs 多模型
        # ==========================================
        if analysis_mode == "single":
            # --- 单模型快速通道 ---
            logger.info("[MultiModelAnalyzer] 单模型模式：跳过综合阶段，直接输出")

            # 获取唯一的那个结果
            single_result = next(iter(successful_results.values()))

            # 阶段4：格式化输出 (92-95%)
            await update_progress("format", 0.92, "正在格式化最终报告...")

            # 构造 aggregated 格式（为了保持返回结构一致）
            aggregated = {
                "unique_risks": [
                    {
                        "risk": item,
                        "source_model": single_result.model_name,
                        "title": item.get("title"),
                        # 补全合并逻辑中产生的字段
                        "reasons": item.get("reasons", []),
                        "suggestions": item.get("suggestions", []),
                        "risk_level": item.get("risk_level"),
                        "confidence": item.get("confidence"),
                        "description": item.get("description"),
                        "source_models": [single_result.model_name],
                        "source_models_count": 1
                    }
                    for item in single_result.risk_items
                ]
            }

            # 直接格式化为 final_result
            final_result = self._format_aggregated_as_final(aggregated)
            await update_progress("format", 0.95, "报告生成完成")

        else:
            # --- 多模型完整流程 ---
            # 阶段3：综合结果 (88-92%)
            await update_progress("synthesize", 0.88, "正在综合多个模型的分析结果...")

            # 4. 中间处理：去重
            aggregated = self._aggregate_and_deduplicate(successful_results)

            # 5. 第二阶段：综合整合
            if self.synthesis_model:
                final_result = self._synthesize_with_final_model(aggregated, context, enhanced_data)
            else:
                final_result = self._fallback_select_best(successful_results)

            await update_progress("synthesize", 0.92, "结果综合完成")

            # 阶段4：格式化输出 (92-95%)
            await update_progress("format", 0.92, "正在格式化最终报告...")
            await update_progress("format", 0.95, "报告生成完成")

        return {
            "stage1_results": {k: self._result_to_dict(v) for k, v in successful_results.items()},
            "aggregated": aggregated,
            "final_result": final_result
        }

    async def _parallel_analyze_subset(
            self,
            models_subset: Dict[str, ChatOpenAI],
            base_prompt: str,
            session_id: str,
            enhanced_data: Optional[Dict]
    ) -> Dict[str, ModelAnalysisResult]:
        """执行指定的模型子集"""
        tasks = []
        for name, model in models_subset.items():
            tasks.append(self._analyze_with_model_stage1(name, model, base_prompt, enhanced_data))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = {}
        for name, result in zip(models_subset.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"[{name}] 分析异常: {result}")
                final_results[name] = ModelAnalysisResult(name, [], "", {}, 0.0, error=str(result))
            else:
                final_results[name] = result

        return final_results

    def _build_context_aware_prompt(
            self,
            raw_context: str,
            rules: List[Dict[str, Any]],
            enhanced_data: Optional[Dict[str, Any]]
    ) -> str:
        """
        构建感知上下文的 User Prompt
        """
        parts = []

        # --- 第一部分：交易全景 (来自 Level 2) ---
        if enhanced_data:
            summary = enhanced_data.get("transaction_summary", "无")
            status = enhanced_data.get("contract_status", "未知")
            parties = enhanced_data.get("parties", [])

            # 格式化主体信息
            parties_str = ", ".join([f"{p.get('name')}({p.get('role')})" for p in parties]) if parties else "未识别"

            parts.extend([
                "## 1. 交易背景",
                f"- **交易综述**: {summary}",
                f"- **当前状态**: {status}",
                f"- **涉及主体**: {parties_str}",
                ""
            ])

        # --- 第二部分：文档内容 ---
        parts.extend([
            "## 2. 待分析文档内容",
            raw_context,
            ""
        ])

        # --- 第三部分：审查规则 (来自 Level 3) ---
        if rules:
            parts.append("## 3. 专项审查规则")
            for i, rule in enumerate(rules, 1):
                parts.append(f"### [规则{i}] {rule.get('rule_name')}")
                parts.append(f"描述: {rule.get('rule_prompt')}")
                parts.append(f"优先级: {rule.get('priority', 5)}")
                parts.append("")
        else:
            parts.append("## 3. 审查要求")
            parts.append("请基于通用商业法律逻辑，全面识别法律、合规及商业风险。")

        # --- 第四部分：输出要求 ---
        parts.extend([
            "\n## 4. 输出格式要求",
            "请严格输出如下 JSON，不要包含 Markdown 代码块标记：",
            """{
  "summary": "简明扼要的风险综述",
  "risk_items": [
    {
      "title": "风险简述",
      "description": "详细说明风险成因及后果",
      "risk_level": "high/medium/low/critical",
      "confidence": 0.9,
      "reasons": ["引用条款或事实依据"],
      "suggestions": ["具体的修改或应对建议"]
    }
  ],
  "total_confidence": 0.85
}"""
        ])

        return "\n".join(parts)

    async def _parallel_analyze_stage1(
            self,
            base_prompt: str,
            session_id: str,
            enhanced_data: Optional[Dict]
    ) -> Dict[str, ModelAnalysisResult]:
        """并行分析"""
        if not self.models:
            return {}

        tasks = []
        for name, model in self.models.items():
            tasks.append(self._analyze_with_model_stage1(name, model, base_prompt, enhanced_data))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = {}
        for name, result in zip(self.models.keys(), results):
            if isinstance(result, Exception):
                logger.error(f"[{name}] 分析异常: {result}")
                final_results[name] = ModelAnalysisResult(name, [], "", {}, 0.0, error=str(result))
            else:
                final_results[name] = result

        return final_results

    async def _analyze_with_model_stage1(
            self,
            name: str,
            model: ChatOpenAI,
            base_prompt: str,
            enhanced_data: Optional[Dict]
    ) -> ModelAnalysisResult:
        """单模型分析执行"""
        # 动态构建 System Prompt
        system_prompt = self._build_system_prompt_for_model(name, enhanced_data)

        try:
            # 优先尝试结构化输出
            try:
                structured_llm = model.with_structured_output(RiskAnalysisExtraction)
                extraction = await structured_llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=base_prompt)
                ])

                return ModelAnalysisResult(
                    model_name=name,
                    risk_items=[item.model_dump() for item in extraction.risk_items],
                    summary=extraction.summary,
                    risk_distribution=self._calculate_distribution(extraction.risk_items),
                    confidence=extraction.total_confidence
                )
            except Exception:
                # 降级到 JSON 解析
                return await self._parse_json_fallback_stage1(name, model, system_prompt, base_prompt)

        except Exception as e:
            return ModelAnalysisResult(name, [], "", {}, 0.0, error=str(e))

    async def _parse_json_fallback_stage1(self, name, model, sys_p, user_p):
        """JSON 解析降级"""
        try:
            res = await model.ainvoke([SystemMessage(content=sys_p), HumanMessage(content=user_p)])
            text = res.content

            # --- 修改点：使用 safe_parse_json ---
            # 移除了原有的 re.sub 清洗逻辑，统一使用工具函数
            data = safe_parse_json(text)
            # ---------------------------------------

            risk_items = data.get("risk_items", [])
            return ModelAnalysisResult(
                model_name=name,
                risk_items=risk_items,
                summary=data.get("summary", ""),
                risk_distribution=self._calculate_distribution_from_items(risk_items),
                confidence=data.get("total_confidence", 0.5),
                raw_response=text
            )
        except Exception as e:
            raise ValueError(f"JSON解析失败: {e}")

    # ==================== 聚合与综合 (保持原有逻辑框架，增加上下文注入) ====================

    def _aggregate_and_deduplicate(self, results: Dict[str, ModelAnalysisResult]) -> Dict[str, Any]:
        """
        汇总去重 (保留原逻辑，效果已经很好)
        """
        all_risks = []
        for model_name, result in results.items():
            for risk in result.risk_items:
                all_risks.append({
                    "risk": risk,
                    "source_model": model_name
                })

        # 简单去重逻辑：基于标题相似度
        unique_risks = []
        used_indices = set()

        for i, item1 in enumerate(all_risks):
            if i in used_indices: continue

            similar_group = [(i, item1)]
            for j, item2 in enumerate(all_risks):
                if j <= i or j in used_indices: continue

                # 相似度计算
                t1 = item1["risk"].get("title", "").lower()
                t2 = item2["risk"].get("title", "").lower()

                if SequenceMatcher(None, t1, t2).ratio() > 0.65:
                    similar_group.append((j, item2))
                    used_indices.add(j)

            # 合并
            merged = self._merge_risks(similar_group)
            unique_risks.append(merged)
            used_indices.add(i)

        return {"unique_risks": unique_risks}

    def _merge_risks(self, group: List[Tuple[int, Dict]]) -> Dict:
        """合并风险点"""
        # 选最好的描述（这里简单选第一个，可优化为选最长的）
        base = group[0][1]["risk"].copy()
        models = [g[1]["source_model"] for g in group]

        # 合并理由和建议
        reasons = set(base.get("reasons", []))
        suggestions = set(base.get("suggestions", []))

        for _, item in group[1:]:
            reasons.update(item["risk"].get("reasons", []))
            suggestions.update(item["risk"].get("suggestions", []))

        base["reasons"] = list(reasons)
        base["suggestions"] = list(suggestions)
        base["source_models"] = list(set(models))
        base["source_models_count"] = len(set(models))

        return base

    def _synthesize_with_final_model(
            self,
            aggregated: Dict,
            context: str,
            enhanced_data: Optional[Dict]
    ) -> Dict:
        """
        综合模型整合：增加对交易逻辑的校验
        """
        risks = aggregated["unique_risks"]

        # 构建 prompt
        narrative = enhanced_data.get("transaction_summary", "") if enhanced_data else ""
        risk_text = json.dumps(risks, ensure_ascii=False, indent=2)

        prompt = f"""作为风险评估总监，请基于以下信息生成最终报告。

## 1. 交易背景
{narrative}

## 2. 各模型识别出的风险点 (待整合)
{risk_text}

## 任务
1. **逻辑校验**：结合交易背景，剔除明显不符合商业逻辑的"幻觉风险"。
2. **描述优化**：将分散的风险点归纳为结构化的风险项，使用专业法律术语。
3. **整体评估**：给出高/中/低风险评级及核心决策建议。

请严格输出 JSON:
{{
  "summary": "...",
  "overall_assessment": {{
    "risk_level": "high/medium/low",
    "core_risks": ["..."],
    "recommendation": "..."
  }},
  "risk_items": [ ...优化后的风险列表... ],
  "total_confidence": 0.9
}}
"""

        try:
            res = self.synthesis_model.invoke([HumanMessage(content=prompt)])
            # 简单的 JSON 提取
            match = re.search(r'\{.*\}', res.content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
        except Exception as e:
            logger.error(f"综合模型失败: {e}")

        return self._format_aggregated_as_final(aggregated)

    def _format_aggregated_as_final(self, aggregated: Dict) -> Dict:
        """降级格式化"""
        risks = aggregated["unique_risks"]
        high_cnt = sum(1 for r in risks if r.get("risk_level") in ["high", "critical"])
        level = "high" if high_cnt > 2 else "medium"

        return {
            "summary": f"共发现 {len(risks)} 个风险点。",
            "overall_assessment": {
                "risk_level": level,
                "core_risks": [r["title"] for r in risks[:3]],
                "recommendation": "请重点关注高风险项。"
            },
            "risk_items": risks,
            "total_confidence": 0.7
        }

    # 辅助函数
    def _calculate_distribution(self, items):
        d = {"high": 0, "medium": 0, "low": 0, "critical": 0}
        for i in items:
            d[i.risk_level.lower()] = d.get(i.risk_level.lower(), 0) + 1
        return d

    def _calculate_distribution_from_items(self, items):
        d = {"high": 0, "medium": 0, "low": 0, "critical": 0}
        for i in items:
            lvl = i.get("risk_level", "low").lower()
            d[lvl] = d.get(lvl, 0) + 1
        return d

    def _result_to_dict(self, res: ModelAnalysisResult) -> Dict:
        from dataclasses import asdict
        return asdict(res)

    def _fallback_select_best(self, results):
        # 简单选第一个成功的
        first = next(iter(results.values()))
        return {
            "summary": first.summary,
            "risk_items": first.risk_items,
            "total_confidence": first.confidence,
            "overall_assessment": {"risk_level": "unknown", "core_risks": [], "recommendation": ""}
        }


def get_multi_model_analyzer() -> MultiModelAnalyzer:
    return MultiModelAnalyzer()