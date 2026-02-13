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
        if getattr(settings, "QWEN3_ENABLED", False) and settings.QWEN3_API_KEY:
            return ChatOpenAI(
                model=settings.QWEN3_MODEL,
                api_key=settings.QWEN3_API_KEY,
                base_url=settings.QWEN3_API_BASE,
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
        生成策略主入口（原始生成 + 强力清洗模式）
        """
        logger.info(f"[StrategyGenerator] 开始生成策略 | 场景: {scenario}")
        logger.info(f"[StrategyGenerator] 输入: case_strength keys={list(case_strength.keys())}")

        try:
            # 1. 验证输入数据
            if not case_strength or case_strength.get("status") == "failed":
                logger.warning(f"[StrategyGenerator] 上游分析失败，使用降级策略")
                return self._get_fallback_strategies(scenario, case_type, "上游分析失败")

            # 2. 提取数据，带默认值
            win_rate = case_strength.get("final_strength", case_strength.get("win_rate_prediction", 0.5))
            analysis_summary = case_strength.get("final_summary", case_strength.get("conclusion", "暂无详细分析"))

            if not analysis_summary or analysis_summary == "暂无详细分析":
                logger.warning(f"[StrategyGenerator] 分析摘要为空，使用降级策略")
                return self._get_fallback_strategies(scenario, case_type, "分析数据不足")

            # 3. 构建 Prompt
            system_prompt = self._build_system_prompt(scenario, case_position)
            user_prompt = self._build_user_prompt(
                case_type, win_rate, analysis_summary, evidence, scenario
            )

            # 4. 强制使用原始调用 (不使用 structured_output)
            try:
                import re

                # 提示 LLM 返回 JSON
                system_prompt += "\n\n请务必只返回纯 JSON 格式，不要包含 Markdown 标记，不要包含其他解释。"

                response = await self.llm.ainvoke([
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_prompt)
                ])

                raw_text = response.content
                logger.info(f"[StrategyGenerator] 原始响应预览(前500字): {raw_text[:500]}...")

                # 5. 强力清洗 JSON
                # 尝试提取 ```json ... ```
                json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
                if json_match:
                    clean_text = json_match.group(1)
                    logger.info(f"[StrategyGenerator] 从 ```json 代码块提取成功")
                else:
                    # 尝试提取第一个 { 到最后一个 }
                    json_match = re.search(r'\{.*\}', raw_text, re.DOTALL)
                    clean_text = json_match.group(0) if json_match else raw_text
                    logger.info(f"[StrategyGenerator] 从原始文本提取 JSON")

                # 6. 解析 JSON
                data_dict = json.loads(clean_text)

                # 兼容两种格式: {"strategies": [...]} 或直接 [...]
                strategies_data = data_dict.get("strategies", []) if isinstance(data_dict, dict) else []
                if not strategies_data and isinstance(data_dict, list):
                    strategies_data = data_dict

                if not strategies_data:
                    logger.warning(f"[StrategyGenerator] 解析后的策略列表为空，使用降级策略")
                    return self._get_fallback_strategies(scenario, case_type, "解析结果为空")

                # 7. 手动构建策略对象（容错处理）
                strategies = []
                for item in strategies_data:
                    try:
                        strategy = {
                            "strategy_id": item.get("strategy_id", f"S_AUTO_{len(strategies)+1}"),
                            "title": item.get("title", "未命名策略"),
                            "type": item.get("type", "balanced"),
                            "description": item.get("description", ""),
                            "steps": [],
                            "expected_outcome": item.get("expected_outcome", ""),
                            "risk_mitigation": item.get("risk_mitigation", ""),
                            "recommendation_score": int(item.get("recommendation_score", 3))
                        }

                        # 处理 steps
                        steps_data = item.get("steps", [])
                        if isinstance(steps_data, list):
                            for step in steps_data:
                                if isinstance(step, dict):
                                    strategy["steps"].append({
                                        "step_name": step.get("step_name", "未命名步骤"),
                                        "description": step.get("description", ""),
                                        "executor": step.get("executor", "律师"),
                                        "deadline": step.get("deadline", "尽快")
                                    })

                        strategies.append(strategy)
                    except Exception as e:
                        logger.warning(f"[StrategyGenerator] 单个策略解析失败: {e}")
                        continue

                if not strategies:
                    logger.warning(f"[StrategyGenerator] 所有策略解析失败，使用降级策略")
                    return self._get_fallback_strategies(scenario, case_type, "策略解析失败")

                # 按推荐分排序
                strategies.sort(key=lambda x: x['recommendation_score'], reverse=True)

                logger.info(f"[StrategyGenerator] 成功生成 {len(strategies)} 条策略")
                return strategies

            except json.JSONDecodeError as je:
                logger.error(f"[StrategyGenerator] JSON解析失败: {je}")
                logger.error(f"[StrategyGenerator] 清洗后的文本(前500字): {clean_text[:500] if 'clean_text' in locals() else 'N/A'}...")
                # 即使 JSON 失败，也尝试把原始文本塞进去
                fallback_strategies = self._get_fallback_strategies(scenario, case_type, "JSON解析失败")
                # 将原始响应添加到第一个策略的描述中
                if fallback_strategies and 'raw_text' in locals():
                    fallback_strategies[0]["description"] += f"\n\n原始LLM响应:\n{raw_text[:1000]}..."
                return fallback_strategies

        except Exception as e:
            logger.error(f"[StrategyGenerator] 策略生成失败: {e}", exc_info=True)
            return self._get_fallback_strategies(scenario, case_type, f"异常: {str(e)}")

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

    def _get_fallback_strategies(self, scenario: str, case_type: str = "", reason: str = "") -> List[Dict[str, Any]]:
        """降级策略（增强版：基于案件类型）"""
        logger.info(f"[StrategyGenerator] 使用降级策略 | scenario={scenario}, case_type={case_type}, reason={reason}")

        base_description = f"系统分析遇到问题（{reason}）。"

        if scenario == "pre_litigation":
            return [{
                "strategy_id": "FALLBACK_PRE_01",
                "title": "补充证据并咨询律师",
                "type": "conservative",
                "description": f"{base_description}建议人工整理证据材料，梳理完整证据链后咨询专业律师。",
                "steps": [
                    {"step_name": "整理证据", "description": "按时间顺序整理所有相关文件", "executor": "当事人", "deadline": "立即"},
                    {"step_name": "咨询律师", "description": "携带材料咨询专业律师", "executor": "当事人", "deadline": "3日内"}
                ],
                "expected_outcome": "明确案情和诉讼可行性",
                "risk_mitigation": "避免诉讼时效届满",
                "recommendation_score": 5
            }]
        elif scenario == "defense":
            return [{
                "strategy_id": "FALLBACK_DEF_01",
                "title": "积极应诉准备",
                "type": "balanced",
                "description": f"{base_description}建议立即查阅法院送达的材料，核实答辩期限。",
                "steps": [
                    {"step_name": "核对材料", "description": "仔细阅读起诉状和证据", "executor": "律师", "deadline": "收到后2日内"},
                    {"step_name": "准备答辩", "description": "起草答辩状", "executor": "律师", "deadline": "答辩期内"}
                ],
                "expected_outcome": "避免缺席审判",
                "risk_mitigation": "保护诉讼权利",
                "recommendation_score": 5
            }]
        elif scenario == "appeal":
            return [{
                "strategy_id": "FALLBACK_APP_01",
                "title": "审查一审判决",
                "type": "conservative",
                "description": f"{base_description}建议仔细审查一审判决书，寻找程序或事实错误。",
                "steps": [
                    {"step_name": "审查判决", "description": "逐条审查一审判决认定的事实和法律适用", "executor": "律师", "deadline": "收到判决后5日内"},
                    {"step_name": "评估上诉", "description": "评估上诉的必要性和可行性", "executor": "律师", "deadline": "上诉期内"}
                ],
                "expected_outcome": "确定上诉策略",
                "risk_mitigation": "避免错过上诉期",
                "recommendation_score": 5
            }]
        else:
            return [{
                "strategy_id": "FALLBACK_DEFAULT_01",
                "title": "寻求专业法律帮助",
                "type": "conservative",
                "description": f"{base_description}建议尽快咨询专业律师。",
                "steps": [
                    {"step_name": "整理材料", "description": "整理所有相关文件", "executor": "当事人", "deadline": "立即"},
                    {"step_name": "法律咨询", "description": "咨询专业律师", "executor": "当事人", "deadline": "3日内"}
                ],
                "expected_outcome": "获得专业指导",
                "risk_mitigation": "避免法律程序失误",
                "recommendation_score": 4
            }]