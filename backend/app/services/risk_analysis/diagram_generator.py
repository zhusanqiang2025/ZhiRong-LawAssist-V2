# backend/app/services/risk_analysis/diagram_generator.py
"""
图表生成服务 (优化版)

专注于生成结构化的图表源代码 (Mermaid/DOT)，由前端负责最终渲染。
这种"后端生成代码-前端渲染图像"的模式具有最佳的兼容性和性能。
"""

import logging
import re
from typing import Dict, List, Any, Optional

from app.schemas.risk_analysis_diagram import (
    DiagramRequest,
    DiagramResult,
    DiagramType,
    DiagramFormat,
    CompanyNode,
    ShareholderNode,
    EquityRelationship,
)

logger = logging.getLogger(__name__)


class DiagramGeneratorService:
    """
    图表生成服务
    """

    def generate(self, request: DiagramRequest) -> DiagramResult:
        """
        生成图表源代码

        Args:
            request: 图表生成请求

        Returns:
            DiagramResult: 包含图表源代码的结果
        """
        # 强制修正格式：对于 Web 应用，始终推荐返回源码
        if request.format not in [DiagramFormat.MERMAID_CODE, DiagramFormat.DOT_CODE]:
            logger.info(f"[DiagramGenerator] 自动将格式 {request.format} 转换为源码模式")
            if "mermaid" in str(request.format).lower():
                request.format = DiagramFormat.MERMAID_CODE
            else:
                request.format = DiagramFormat.DOT_CODE

        try:
            if request.diagram_type == DiagramType.EQUITY_STRUCTURE:
                return self._generate_equity_mermaid(request)
            elif request.diagram_type == DiagramType.EQUITY_PENETRATION:
                return self._generate_equity_graphviz(request)
            elif request.diagram_type == DiagramType.INVESTMENT_FLOW:
                return self._generate_flowchart_mermaid(request)
            elif request.diagram_type == DiagramType.RISK_MINDMAP:
                return self._generate_mindmap_mermaid(request)
            elif request.diagram_type == DiagramType.RELATIONSHIP_GRAPH:
                return self._generate_relationships_mermaid(request)
            elif request.diagram_type == DiagramType.TIMELINE:
                return self._generate_timeline_mermaid(request)
            else:
                raise ValueError(f"不支持的图表类型: {request.diagram_type}")

        except Exception as e:
            logger.error(f"[DiagramGenerator] 生成失败: {e}", exc_info=True)
            return DiagramResult(
                diagram_type=request.diagram_type,
                format=request.format,
                title=request.title,
                source_code="",
                metadata={"error": str(e)}
            )

    # ==================== Mermaid 生成器 ====================

    def _generate_equity_mermaid(self, request: DiagramRequest) -> DiagramResult:
        """生成股权结构图 (Mermaid)"""
        lines = ["graph BT"] # Bottom to Top (子公司指向母公司)
        
        # 定义样式
        lines.append("classDef company fill:#e1f5fe,stroke:#01579b,stroke-width:2px;")
        lines.append("classDef person fill:#fff3e0,stroke:#e65100,stroke-width:2px;")
        
        # 添加节点
        for company in request.companies:
            nid = self._sanitize_id(company.name)
            label = self._truncate_label(company.name)
            lines.append(f'{nid}["{label}"]:::company')
            
        for person in request.shareholders:
            nid = self._sanitize_id(person.name)
            label = self._truncate_label(person.name)
            style = "person" if person.type == "person" else "company"
            shape_l, shape_r = ("(", ")") if person.type == "person" else ("[", "]")
            lines.append(f'{nid}{shape_l}"{label}"{shape_r}:::{style}')

        # 添加关系
        for rel in request.relationships:
            sid = self._sanitize_id(rel.source)
            tid = self._sanitize_id(rel.target)
            ratio = rel.ratio if rel.ratio else ""
            lines.append(f'{sid} -->|{ratio}| {tid}')

        return self._build_result(request, "\n".join(lines), "mermaid")

    def _generate_flowchart_mermaid(self, request: DiagramRequest) -> DiagramResult:
        """生成流程图 (Mermaid)"""
        steps = request.additional_data.get("steps", [])
        lines = ["graph LR"]
        
        for i, step in enumerate(steps):
            sid = f"s{i}"
            label = step.get("label", "") if isinstance(step, dict) else str(step)
            lines.append(f'{sid}["{label}"]')
            if i > 0:
                lines.append(f"s{i-1} --> {sid}")
                
        return self._build_result(request, "\n".join(lines), "mermaid")

    def _generate_mindmap_mermaid(self, request: DiagramRequest) -> DiagramResult:
        """生成思维导图 (Mermaid)"""
        risks = request.additional_data.get("risks", {})
        lines = ["mindmap"]
        root_label = request.title or "风险分析"
        lines.append(f"  root(({root_label}))")
        
        # 递归生成节点
        def add_nodes(data, indent=4):
            if isinstance(data, dict):
                for k, v in data.items():
                    lines.append(f"{' '*indent}{k}")
                    add_nodes(v, indent + 2)
            elif isinstance(data, list):
                for item in data:
                    lines.append(f"{' '*indent}{item}")
        
        add_nodes(risks)
        return self._build_result(request, "\n".join(lines), "mermaid")

    def _generate_timeline_mermaid(self, request: DiagramRequest) -> DiagramResult:
        """生成时间线 (Mermaid)"""
        events = request.additional_data.get("events", [])
        lines = ["timeline"]
        if request.title:
            lines.append(f"title {request.title}")
            
        # 按日期排序
        sorted_events = sorted(events, key=lambda x: x.get("date", "0000"))
        
        for event in sorted_events:
            date = event.get("date", "未知日期")
            desc = event.get("event", "") or event.get("description", "")
            # Mermaid timeline 格式: 2023-01 : 事件内容
            lines.append(f"    {date} : {desc}")
            
        return self._build_result(request, "\n".join(lines), "mermaid")

    def _generate_relationships_mermaid(self, request: DiagramRequest) -> DiagramResult:
        """生成文档关系图 (Mermaid Force Layout or Graph)"""
        # 使用 graph 布局
        lines = ["graph LR"]
        rels = request.additional_data.get("relationships", [])
        
        for rel in rels:
            s = self._sanitize_id(rel.get("doc1", rel.get("source", "")))
            t = self._sanitize_id(rel.get("doc2", rel.get("target", "")))
            label = rel.get("relationship", rel.get("type", ""))
            
            # 不同的关系使用不同的线条
            if "补充" in label or "附件" in label:
                arrow = "-.->"
            elif "冲突" in label or "争议" in label:
                arrow = "x-x"
                label = f"MISSING:{label}" # 红色警告
            else:
                arrow = "-->"
                
            lines.append(f'{s} {arrow}|{label}| {t}')
            
        return self._build_result(request, "\n".join(lines), "mermaid")

    # ==================== Graphviz 生成器 ====================
    
    def _generate_equity_graphviz(self, request: DiagramRequest) -> DiagramResult:
        """生成复杂股权穿透图 (Graphviz DOT)"""
        lines = [
            'digraph G {',
            '  rankdir="BT";', # Bottom to Top
            '  node [shape=box, style="rounded,filled", fontname="Microsoft YaHei"];',
            '  edge [fontname="Microsoft YaHei"];'
        ]
        
        # 节点
        for company in request.companies:
            nid = self._sanitize_id(company.name)
            lines.append(f'  {nid} [label="{company.name}", fillcolor="lightblue"];')
            
        for sh in request.shareholders:
            nid = self._sanitize_id(sh.name)
            shape = "ellipse" if sh.type == "person" else "box"
            color = "orange" if sh.type == "person" else "lightblue"
            lines.append(f'  {nid} [label="{sh.name}", shape={shape}, fillcolor="{color}"];')
            
        # 边
        for rel in request.relationships:
            s = self._sanitize_id(rel.source)
            t = self._sanitize_id(rel.target)
            lines.append(f'  {s} -> {t} [label="{rel.ratio}"];')
            
        lines.append('}')
        
        return self._build_result(request, "\n".join(lines), "graphviz")

    # ==================== 辅助方法 ====================

    def _build_result(self, req: DiagramRequest, code: str, engine: str) -> DiagramResult:
        return DiagramResult(
            diagram_type=req.diagram_type,
            format=req.format,
            title=req.title,
            source_code=code,
            metadata={"engine": engine}
        )

    def _sanitize_id(self, name: str) -> str:
        """清理ID：移除空格、特殊字符，确保唯一性"""
        if not name: return "node_unknown"
        # 仅保留中英文和数字
        clean = re.sub(r'[^\w\u4e00-\u9fa5]', '_', str(name))
        # 截断过长ID
        if len(clean) > 20:
            import hashlib
            hash_suffix = hashlib.md5(name.encode()).hexdigest()[:4]
            clean = clean[:15] + hash_suffix
        # 确保不以数字开头
        if clean[0].isdigit():
            clean = "n" + clean
        return clean

    def _truncate_label(self, label: str, max_len: int = 15) -> str:
        """截断过长的显示标签"""
        if len(label) > max_len:
            return label[:max_len] + "..."
        return label

def get_diagram_generator_service() -> DiagramGeneratorService:
    return DiagramGeneratorService()