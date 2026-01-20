# backend/app/services/litigation_analysis/strategy_generator.py
"""
策略生成器 (Strategy Generator)

职责：
1. "行动指挥官"：将前面的分析结论（法律/事实/胜算）转化为具体的行动指南。
2. 动态策略规划：
   - 根据胜诉率高低，推荐 激进(Aggressive) / 稳健(Balanced) / 保守(Conservative) 方案。
   - 根据场景差异，生成 财产保全 / 管辖权异议 / 证据突袭 等特定战术。
"""

import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.core.config import settings

logger = logging.getLogger(__name__)


# ==================== 数据模型 ====================

class ActionStep(BaseModel):
    """具体的行动步骤"""
    step_name: str = Field(..., description="步骤名称")
    description: str = Field(..., description="具体操作说明")
    executor: str = Field(..., description="建议执行人 (律师/当事人/调查员)")
    deadline: str = Field(..., description="建议完成时限 (如：立案前/开庭前3天)")

class LitigationStrategy(BaseModel):
    """完整的诉讼策略方案"""
    strategy_id: str = Field(..., description="策略ID (如 S_AGGRESSIVE_01)")
    title: str = Field(..., description="策略名称 (如：快速保全施压策略)")
    type: str = Field(..., description="类型 (aggressive/balanced/conservative/settlement)")
    description: str = Field(..., description="策略核心逻辑概述")
    
    # 核心：具体怎么做
    steps: List[ActionStep] = Field(..., description="执行步骤清单")
    
    # 预期效果与风险
    expected_outcome: str = Field(..., description="预期达到的效果")
    risk_mitigation: str = Field(..., description="针对该策略风险的应对措施")
    
    recommendation_score: int = Field(..., description="推荐指数 (1-5星)")


class StrategyList(BaseModel):
    """策略列表容器"""
    strategies: List[LitigationStrategy]


# ==================== 生成器实现 ====================

class StrategyGenerator:
    """
    智能策略生成器
    """

    def __init__(self):
        # 优先使用 Qwen3 或 DeepSeek 进行规划，因为策略生成需要较强的逻辑规划能力
        self.llm = self._init_llm()

    def _init_llm(self) -> ChatOpenAI:
        """初始化 LLM (复用配置逻辑)"""
        # 优先 Qwen3 (长文本规划能力强)
        if getattr(settings, "QWEN3_THINKING_ENABLED", False) and settings.QWEN3_THINKING_API_KEY:
            return ChatOpenAI(
                model=settings.QWEN3_THINKING_MODEL,
                api_key=settings.QWEN3_THINKING_API_KEY,
                base_url=settings.QWEN3_THINKING_API_URL,
                temperature=0.3, # 策略需要一点灵活性
                max_tokens=4000
            )
        # 其次 DeepSeek
        elif settings.DEEPSEEK_API_KEY:
            return ChatOpenAI(
                model="deepseek-chat",
                api_key=settings.DEEPSEEK_API_KEY,
                base_url=settings.DEEPSEEK_API_URL,
                temperature=0.3
            )
        # 兜底
        else:
            # 假设一定有可用的配置，否则在上一步就会报错
            return ChatOpenAI(api_key="dummy") 

    async def generate(
        self,
        case_strength: Dict[str, Any],
        evidence: Dict[str, Any],
        case_type: str,
        case_position: str,
        scenario: str = "pre_litigation"
    ) -> List[Dict[str, Any]]:
        """
        生成策略主入口

        Args:
            case_strength: 来自 MultiModelAnalyzer 的结果 (包含 win_rate, risks 等)
            evidence: 来自 EvidenceAnalyzer 的结果 (包含 gaps, impeachment 等)
            case_type: 案由
            case_position: 地位
            scenario: 场景

        Returns:
            List[Dict]: 策略列表
        """
        logger.info(f"[StrategyGenerator] 开始生成策略 | 场景: {scenario}")

        try:
            # 1. 准备上下文
            # 如果上一步分析失败，这里可能拿不到完整数据，需要做容错
            win_rate = case_strength.get("final_strength", 0.5)
            analysis_summary = case_strength.get("final_summary", "暂无详细分析")
            
            # 2. 构建 Prompt
            system_prompt = self._build_system_prompt(scenario, case_position)
            user_prompt = self._build_user_prompt(
                case_type, win_rate, analysis_summary, evidence, scenario
            )

            # 3. 调用 LLM
            structured_llm = self.llm.with_structured_output(StrategyList)
            result = await structured_llm.ainvoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_prompt)
            ])

            # 4. 空值检查
            if result is None:
                logger.error("[StrategyGenerator] LLM 返回结果为空")
                return self._get_fallback_strategies(scenario)

            # 5. 格式化输出
            strategies = [strategy.dict() for strategy in result.strategies]
            
            # 按推荐分排序
            strategies.sort(key=lambda x: x['recommendation_score'], reverse=True)
            
            logger.info(f"[StrategyGenerator] 生成了 {len(strategies)} 条策略")
            return strategies

        except Exception as e:
            logger.error(f"[StrategyGenerator] 策略生成失败: {e}", exc_info=True)
            return self._get_fallback_strategies(scenario)

    def _build_system_prompt(self, scenario: str, position: str) -> str:
        """构建人设"""
        role = "资深诉讼律师"
        base = f"你是一位{role}，善于根据案件局势制定务实、可落地的诉讼策略。"
        
        if scenario == "pre_litigation":
            return f"{base} 客户正准备起诉（{position}）。你需要根据胜诉率高低，分别提供激进（直接起诉+保全）或稳健（发函+谈判）的方案。"
        elif scenario == "defense":
            return f"{base} 客户是被告（{position}）。你需要利用程序规则（管辖/时效）拖延时间，或利用证据漏洞进行实质抗辩，甚至通过反诉以打促和。"
        elif scenario == "appeal":
            return f"{base} 客户准备上诉。二审改判难度大，你需要制定精准打击一审程序或事实错误的方案。"
        else:
            return base

    def _build_user_prompt(
        self, 
        case_type: str, 
        win_rate: float, 
        summary: str,
        evidence: Dict[str, Any],
        scenario: str
    ) -> str:
        """构建上下文"""
        
        # 1. 证据情报
        evidence_info = ""
        if scenario == "pre_litigation":
            missing = evidence.get("missing_evidence", [])
            evidence_info = f"目前证据缺口: {', '.join(missing)}" if missing else "证据链基本完整"
        elif scenario == "defense":
            points = evidence.get("impeachment_strategy", [])
            evidence_info = f"主要质证点: {'; '.join(points)}" if points else "暂未发现明显证据漏洞"

        # 2. 态势判断
        situation = ""
        if win_rate > 0.7:
            situation = "我方优势明显。重点在于快速锁定胜局，防止对方转移财产。"
        elif win_rate < 0.4:
            situation = "我方处于劣势。重点在于降低损失，争取调解，或寻找程序性突破口。"
        else:
            situation = "双方势均力敌。重点在于证据补强和庭审博弈。"

        prompt = f"""
请为【{case_type}】案件制定 2-3 套具体的行动策略。

【案件态势】
- 胜诉率预估: {win_rate * 100:.1f}%
- 核心分析: {summary}
- 证据情况: {evidence_info}
- 战略定调: {situation}

【生成要求】
1. 必须生成至少 2 种不同风格的策略（例如：激进型 vs 保守型/调解型）。
2. "steps" 必须是具体的行动（如：去哪里调取什么文件，向法院提交什么申请）。
3. 必须包含具体的风险应对措施。
4. 严格按照 JSON 格式输出。
"""
        return prompt

    def _get_fallback_strategies(self, scenario: str) -> List[Dict[str, Any]]:
        """降级策略 (LLM 挂了时的兜底)"""
        if scenario == "pre_litigation":
            return [{
                "strategy_id": "FALLBACK_01",
                "title": "补充证据并咨询律师",
                "type": "conservative",
                "description": "系统分析遇到问题。建议人工整理证据材料，梳理完整证据链后咨询专业律师。",
                "steps": [],
                "expected_outcome": "明确案情",
                "risk_mitigation": "无",
                "recommendation_score": 3
            }]
        else:
            return [{
                "strategy_id": "FALLBACK_02",
                "title": "积极应诉准备",
                "type": "balanced",
                "description": "建议立即查阅法院送达的材料，核实答辩期限，避免缺席审判。",
                "steps": [],
                "expected_outcome": "避免程序失权",
                "risk_mitigation": "无",
                "recommendation_score": 5
            }]