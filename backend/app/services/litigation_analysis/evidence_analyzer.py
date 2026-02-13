# backend/app/services/litigation_analysis/evidence_analyzer.py
"""
证据分析器 (Evidence Analyzer)

职责：
1. 对照 CaseRuleAssembler 提供的法律规则，对案件材料进行专项审查。
2. 执行"三性"分析（真实性、合法性、关联性）。
3. 根据场景差异输出不同的分析结果：
   - 起诉场景：输出"证据清单"和"补证建议" (Gap Analysis)
   - 应诉场景：输出"质证意见" (Impeachment)
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime

from app.services.common.deepseek_service import DeepseekService
# 假设有一个通用的 Prompt 构建器或工具类，这里简化为内部方法

logger = logging.getLogger(__name__)


class EvidenceAnalyzer:
    """
    智能证据分析器
    """

    def __init__(self, llm_service=None):
        self.llm_service = llm_service or DeepseekService()

    async def analyze(
        self,
        documents: Dict[str, Any],
        case_type: str,
        context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        执行证据分析

        Args:
            documents: 预整理后的案件文档 (preorganized_case)
            case_type: 案件类型
            context: 上下文，必须包含:
                     - rules: CaseRuleAssembler 生成的规则指令列表
                     - scenario: 分析场景 (pre_litigation/defense/etc.)

        Returns:
            Dict: 结构化的证据分析结果
        """
        context = context or {}
        rules = context.get("rules", [])
        scenario = context.get("scenario", "pre_litigation")
        
        logger.info(f"[EvidenceAnalyzer] 开始分析证据 | 场景: {scenario} | 规则数: {len(rules)}")

        # 1. 准备分析素材
        # 将结构化的文档列表转换为 LLM 可读的清单
        evidence_list_text = self._format_evidence_list(documents)
        
        if not evidence_list_text:
            logger.warning("[EvidenceAnalyzer] 没有可分析的证据材料")
            return self._get_empty_result()

        # 2. 构建针对性的 Prompt
        # 这里将"规则"和"证据"结合，要求 LLM 进行碰撞
        prompt = self._build_evidence_prompt(evidence_list_text, rules, scenario, case_type)
        
        # 3. 调用 LLM
        try:
            response = await self.llm_service.chat_completion(
                messages=[
                    {"role": "system", "content": self._get_system_prompt(scenario)},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1 # 证据分析要求严谨，低温度
            )
            
            # 4. 解析结果
            result = self._parse_llm_result(response)
            
            # 5. 后处理：计算简单的统计指标
            result["stats"] = {
                "total_count": len(documents.get("document_analyses", [])),
                "analyzed_at": datetime.now().isoformat()
            }
            
            logger.info(f"[EvidenceAnalyzer] 分析完成 | 发现问题/要点数: {len(result.get('analysis_points', []))}")
            return result

        except Exception as e:
            logger.error(f"[EvidenceAnalyzer] 分析失败: {e}", exc_info=True)
            return self._get_empty_result(error=str(e))

    def _format_evidence_list(self, documents: Dict[str, Any]) -> str:
        """格式化证据清单"""
        if not documents or "document_analyses" not in documents:
            return ""

        lines = []
        for idx, doc in enumerate(documents["document_analyses"], 1):
            # 仅列出与证据相关的信息
            lines.append(f"证据{idx}: 【{doc.get('file_name', '未知文件')}】")
            lines.append(f"   - 类型: {doc.get('file_type', '未知')}")
            lines.append(f"   - 核心内容: {doc.get('content_summary', '')[:100]}...")
            
            # 如果有识别出的关键要素，也带上
            if doc.get('key_dates'):
                lines.append(f"   - 提及日期: {', '.join(doc['key_dates'])}")
        
        return "\n".join(lines)

    def _build_evidence_prompt(
        self, 
        evidence_text: str, 
        rules: List[str], 
        scenario: str,
        case_type: str
    ) -> str:
        """构建 Prompt"""
        
        # 1. 场景指令差异化
        task_instruction = ""
        if scenario == "pre_litigation":
            task_instruction = (
                "你的目标是【审查证据充分性】。\n"
                "1. 对照规则，检查现有证据是否满足立案和胜诉的基本要求。\n"
                "2. 找出缺失的关键证据（Gap Analysis）。\n"
                "3. 评估证据的证明力强弱。"
            )
        elif scenario == "defense":
            task_instruction = (
                "你的目标是【寻找证据漏洞】。\n"
                "1. 模拟被告律师视角，对上述材料进行严厉的质证。\n"
                "2. 重点审查：真实性存疑、来源不合法、与待证事实无关联的地方。\n"
                "3. 寻找能够推翻对方主张的矛盾点。"
            )
        elif scenario == "appeal":
            task_instruction = (
                "你的目标是【审查认定事实错误】。\n"
                "1. 分析一审判决认定的事实是否有证据支撑。\n"
                "2. 寻找证据采信过程中的逻辑错误。"
            )
        else:
            task_instruction = "请对提供的证据材料进行法律分析，评估其证明力。"

        # 2. 注入规则 (这些规则来自数据库)
        rules_text = "\n".join(rules) if rules else "（使用通用法律常识）"

        prompt = f"""
## 任务目标
{task_instruction}

## 案件类型
{case_type}

## 审查规则 (必须严格遵守)
{rules_text}

## 待审查证据材料
{evidence_text}

## 输出要求
请返回 JSON 格式结果，包含以下字段：
1. "analysis_points": [List] 具体的分析要点，每点包含 "evidence_ref"(涉及证据), "issue"(问题/亮点), "legal_implication"(法律后果)。
2. "admissibility_assessment": "整体三性评估结论"。
3. "missing_evidence": [List] 建议补充的证据清单 (仅起诉场景)。
4. "impeachment_strategy": [List] 质证策略 (仅应诉场景)。
5. "risk_level": "low/medium/high"。

请只返回 JSON 数据，不要包含其他 Markdown 标记。
"""
        return prompt

    def _get_system_prompt(self, scenario: str) -> str:
        role = "原告律师" if scenario == "pre_litigation" else "被告律师"
        return f"你是一位经验丰富的{role}，擅长证据规则和法庭质证。请以极其严谨、挑剔的眼光分析证据。"

    def _parse_llm_result(self, response: str) -> Dict[str, Any]:
        """解析 LLM 返回的 JSON"""
        try:
            # 清理可能的 Markdown 代码块标记
            cleaned = response.replace("```json", "").replace("```", "").strip()
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start != -1 and end > start:
                json_str = cleaned[start:end]
                return json.loads(json_str)
            else:
                raise ValueError("未找到有效的 JSON 结构")
        except Exception as e:
            logger.warning(f"JSON 解析失败: {e}, 返回原始内容")
            return {
                "raw_analysis": response,
                "analysis_points": [],
                "error": "解析失败"
            }

    def _get_empty_result(self, error: str = None) -> Dict[str, Any]:
        """返回空结果结构"""
        return {
            "analysis_points": [],
            "admissibility_assessment": "无法分析",
            "missing_evidence": [],
            "impeachment_strategy": [],
            "risk_level": "unknown",
            "error": error
        }