# backend/app/services/litigation_analysis/report_generator.py
"""
报告生成器 (Report Generator)

职责：
1. 数据汇聚：收集工作流中各节点产生的数据（预整理、规则、证据、模型推理、策略）。
2. 格式渲染：将结构化数据渲染为人类可读的 Markdown 报告。
3. 结构化输出：同时返回 JSON 数据供前端组件渲染（如仪表盘、图表）。
"""

import json
import logging
from typing import Dict, Any, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    智能报告生成器
    """

    def generate(self, report_data: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        """
        生成报告主入口

        Args:
            report_data: 包含所有分析结果的字典
                - case_type, case_position, scenario
                - model_results (MultiModelAnalyzer output)
                - evidence_analysis (EvidenceAnalyzer output)
                - strategies (StrategyGenerator output)
                - timeline, rules, etc.
                - draft_documents: 已废弃（阶段3按需生成，不再包含在报告中）

        Returns:
            (markdown_content, json_data)
        """
        scenario = report_data.get("scenario", "pre_litigation")
        logger.info(f"[ReportGenerator] 开始生成报告 | 场景: {scenario}")

        try:
            # 1. 提取核心数据
            model_res = report_data.get("model_results", {})
            strategies = report_data.get("strategies", [])
            evidence = report_data.get("evidence_analysis", {})
            # draft_docs = report_data.get("draft_documents", [])  # 已废弃：阶段3按需生成

            # 2. 构建 Markdown 章节
            sections = []

            # 2.1 标题与基本信息
            sections.append(self._render_header(report_data))

            # 2.2 核心结论 (胜诉率/总结)
            sections.append(self._render_executive_summary(model_res, scenario))

            # 2.3 事实与时间线
            sections.append(self._render_facts_and_timeline(model_res, report_data.get("timeline")))

            # 2.4 法律分析 (规则应用)
            sections.append(self._render_legal_analysis(model_res, report_data.get("rules")))

            # 2.5 证据分析 (三性/缺口)
            sections.append(self._render_evidence_analysis(evidence, scenario))

            # 2.6 行动策略
            sections.append(self._render_strategies(strategies))

            # 2.7 法律文书草稿（已移除 - 改为阶段3按需生成）
            # if draft_docs:
            #     sections.append(self._render_draft_documents(draft_docs))

            # 2.8 免责声明
            sections.append(self._render_disclaimer())

            # 3. 组合最终报告
            final_markdown = "\n\n".join(sections)

            # 4. 准备 JSON 数据 (供前端图表使用)
            final_json = self._build_json_output(report_data, model_res, strategies)

            return final_markdown, final_json

        except Exception as e:
            logger.error(f"[ReportGenerator] 报告生成失败: {e}", exc_info=True)
            return self._generate_error_report(str(e))

    def _render_header(self, data: Dict[str, Any]) -> str:
        """渲染报告头"""
        title_map = {
            "pre_litigation": "诉讼可行性评估报告",
            "defense": "应诉策略分析报告",
            "appeal": "二审上诉评估报告",
            "execution": "执行线索分析报告"
        }
        title = title_map.get(data.get("scenario"), "法律案件分析报告")
        
        return f"""# {title}

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M')}
**案件类型**: {data.get('case_type')}
**您的地位**: {data.get('case_position')}
---"""

    def _render_executive_summary(self, model_res: Dict[str, Any], scenario: str) -> str:
        """渲染核心摘要"""
        win_rate = model_res.get("final_strength", 0.0)
        summary = model_res.get("final_summary", "暂无分析摘要")
        confidence = model_res.get("confidence", 0.0)
        
        # 胜诉率可视化文本
        rate_text = f"{win_rate * 100:.1f}%"
        rate_desc = ""
        if win_rate > 0.7: rate_desc = "(较高胜算)"
        elif win_rate < 0.4: rate_desc = "(风险较大)"
        else: rate_desc = "(胜负难料)"

        score_label = "预估胜诉率" if scenario == "pre_litigation" else "预估抗辩/上诉成功率"

        return f"""## 1. 核心结论

### {score_label}: **{rate_text}** {rate_desc}
> 模型置信度: {confidence * 100:.0f}%

**案情综述**:
{summary}

**最终意见**:
{model_res.get('conclusion', '无')}
"""

    def _render_facts_and_timeline(self, model_res: Dict[str, Any], timeline: Dict[str, Any]) -> str:
        """渲染事实认定"""
        facts = model_res.get("final_facts", [])
        
        md = ["## 2. 事实认定与时间线", "### 经认定的关键法律事实"]
        if facts:
            for fact in facts:
                md.append(f"- {fact}")
        else:
            md.append("- (未提取到关键事实)")

        if timeline and timeline.get("events"):
            md.append("\n### 关键时间节点")
            # 简单的 Markdown 表格
            md.append("| 日期 | 事件 | 来源 |")
            md.append("| :--- | :--- | :--- |")
            for event in timeline.get("events", [])[:5]: # 只展示前5个关键节点
                date = event.get('date', '')
                desc = event.get('description', '')
                src = event.get('source_file', '未知')
                md.append(f"| {date} | {desc} | {src} |")
        
        return "\n".join(md)

    def _render_legal_analysis(self, model_res: Dict[str, Any], rules: List[str]) -> str:
        """渲染法律分析"""
        args = model_res.get("final_legal_arguments", [])
        rule_apps = model_res.get("rule_application", [])
        strengths = model_res.get("final_strengths", [])
        weaknesses = model_res.get("final_weaknesses", [])

        md = ["## 3. 法律分析"]
        
        md.append("### 3.1 核心主张/抗辩")
        for arg in args:
            md.append(f"> {arg}")
            
        md.append("\n### 3.2 规则适用")
        if rule_apps:
            for app in rule_apps:
                md.append(f"- {app}")
        else:
            md.append("- (未生成具体的规则适用分析)")

        md.append("\n### 3.3 优劣势分析 (SWOT)")
        md.append("**有利因素 (Strengths)**:")
        for s in strengths:
            md.append(f"- ✅ {s}")
            
        md.append("\n**不利因素/风险 (Weaknesses)**:")
        for w in weaknesses:
            md.append(f"- ⚠️ {w}")

        return "\n".join(md)

    def _render_evidence_analysis(self, evidence: Dict[str, Any], scenario: str) -> str:
        """渲染证据分析"""
        if not evidence:
            return ""
            
        md = ["## 4. 证据审查"]
        
        assessment = evidence.get("admissibility_assessment", "暂无")
        md.append(f"**整体评价**: {assessment}")
        
        points = evidence.get("analysis_points", [])
        if points:
            md.append("\n**具体审查意见**:")
            for p in points:
                # 兼容不同的数据结构
                issue = p.get('issue') or p.get('point', '')
                ref = p.get('evidence_ref', '')
                md.append(f"- **{ref}**: {issue}")

        # 场景化输出
        if scenario == "pre_litigation":
            missing = evidence.get("missing_evidence", [])
            if missing:
                md.append("\n### ❗ 证据缺口 (必须补充)")
                for m in missing:
                    md.append(f"- [ ] {m}")
        
        elif scenario == "defense":
            impeach = evidence.get("impeachment_strategy", [])
            if impeach:
                md.append("\n### 🛡️ 质证策略")
                for i in impeach:
                    md.append(f"- {i}")

        return "\n".join(md)

    def _render_strategies(self, strategies: List[Dict[str, Any]]) -> str:
        """渲染行动策略"""
        if not strategies:
            return ""

        md = ["## 5. 行动建议方案"]

        for idx, strat in enumerate(strategies, 1):
            rec_icon = "⭐" * strat.get('recommendation_score', 0)
            title = strat.get('title', '策略')
            desc = strat.get('description', '')

            md.append(f"### 方案 {idx}: {title} {rec_icon}")
            md.append(f"{desc}\n")

            steps = strat.get('steps', [])
            if steps:
                md.append("**执行步骤**:")
                for step_idx, step in enumerate(steps, 1):
                    # 兼容对象或字典
                    s_name = step.get('step_name') if isinstance(step, dict) else step.step_name
                    s_desc = step.get('description') if isinstance(step, dict) else step.description
                    md.append(f"{step_idx}. **{s_name}**: {s_desc}")

            risk_mit = strat.get('risk_mitigation')
            if risk_mit:
                md.append(f"\n**💡 风险应对**: {risk_mit}")

            md.append("---")

        return "\n".join(md)

    def _render_draft_documents(self, draft_docs: List[Dict[str, Any]]) -> str:
        """
        渲染法律文书草稿（新增）

        展示生成的法律文书草稿，包括：
        - 起诉状/答辩状
        - 证据清单
        - 申请书等
        """
        if not draft_docs:
            return ""

        md = ["## 6. 法律文书草稿"]

        for doc in draft_docs:
            doc_name = doc.get('document_name', '文书')
            doc_type = doc.get('document_type', '')
            content = doc.get('content', '')
            placeholders = doc.get('placeholders', [])
            generated_at = doc.get('generated_at', '')

            md.append(f"### 📄 {doc_name}")

            # 显示占位符提示
            if placeholders:
                md.append(f"**⚠️ 需要填写的信息**: {', '.join(placeholders)}")

            # 显示文书内容（使用折叠区域）
            md.append("\n<details>")
            md.append(f"<summary>点击查看 {doc_name} 完整内容</summary>\n")
            md.append("\n```\n")
            md.append(content)
            md.append("\n```\n")
            md.append("</details>")

            md.append("---")

        md.append("\n💡 **提示**: 上述文书为 AI 生成的草稿，请务必仔细核对并根据实际情况修改后使用。")

        return "\n".join(md)

    def _render_disclaimer(self) -> str:
        """渲染免责声明"""
        return """
> **免责声明**: 
> 本报告由人工智能系统辅助生成，仅供法律专业人士参考，不构成正式的法律意见或担保。
> 法律结果受多种不可控因素影响，请务必咨询专业律师以获得针对性指导。
"""

    def _build_json_output(
        self,
        raw_data: Dict[str, Any],
        model_res: Dict[str, Any],
        strategies: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """构建前端可用的 JSON 数据结构"""
        return {
            "meta": {
                "generated_at": datetime.now().isoformat(),
                "case_type": raw_data.get("case_type"),
                "scenario": raw_data.get("scenario"),
                "draft_documents_available": True  # 提示前端可以调用阶段3生成文书
            },
            "dashboard": {
                "win_rate": model_res.get("final_strength", 0),
                "confidence": model_res.get("confidence", 0),
                "key_facts_count": len(model_res.get("final_facts", [])),
                "risk_count": len(model_res.get("final_weaknesses", [])),
                "strategies_count": len(strategies)  # 策略数量
            },
            "content": {
                "summary": model_res.get("final_summary"),
                "facts": model_res.get("final_facts"),
                "timeline": raw_data.get("timeline"),
                "strategies": strategies
                # draft_documents 已移除 - 改为阶段3按需生成
            }
        }

    def _generate_error_report(self, error_msg: str) -> Tuple[str, Dict[str, Any]]:
        """生成错误报告"""
        md = f"""# 分析报告生成失败
        
很抱歉，在生成报告的过程中遇到了技术问题。

**错误信息**: {error_msg}

请检查输入数据或联系管理员。
"""
        return md, {"error": error_msg}