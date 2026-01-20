# backend/app/schemas/risk_analysis_diagram.py
"""
图表生成服务的 Pydantic Schema 定义

用于图表生成的数据验证和序列化
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class DiagramType(str, Enum):
    """图表类型"""
    EQUITY_STRUCTURE = "equity_structure"        # 股权结构图
    EQUITY_PENETRATION = "equity_penetration"    # 股权穿透图
    INVESTMENT_FLOW = "investment_flow"          # 投资流程图
    RISK_MINDMAP = "risk_mindmap"                # 风险思维导图
    RELATIONSHIP_GRAPH = "relationship_graph"    # 关系图
    TIMELINE = "timeline"                        # 时间线


class DiagramFormat(str, Enum):
    """输出格式"""
    SVG = "svg"
    PNG = "png"
    PDF = "pdf"
    MERMAID_CODE = "mermaid"  # Mermaid 源代码（前端渲染）
    DOT_CODE = "dot"          # Graphviz DOT 源代码


class CompanyNode(BaseModel):
    """公司节点"""
    name: str = Field(..., description="公司名称")
    registration_code: Optional[str] = Field(None, description="统一社会信用代码")
    legal_representative: Optional[str] = Field(None, description="法定代表人")
    registered_capital: Optional[str] = Field(None, description="注册资本")
    node_type: str = Field(default="company", description="节点类型：company/person")


class ShareholderNode(BaseModel):
    """股东节点"""
    name: str = Field(..., description="股东名称")
    node_type: str = Field(default="person", description="节点类型：company/person")


class EquityRelationship(BaseModel):
    """股权关系"""
    source: str = Field(..., description="股东名称")
    target: str = Field(..., description="被投资公司名称")
    ratio: str = Field(..., description="持股比例（如 '51%'）")
    amount: Optional[str] = Field(None, description="出资金额")
    relationship_type: str = Field(default="equity", description="关系类型：equity/control/actual_control")


class DiagramRequest(BaseModel):
    """图表生成请求"""
    diagram_type: DiagramType
    format: DiagramFormat = Field(default=DiagramFormat.MERMAID_CODE)
    title: Optional[str] = Field(None, description="图表标题")
    companies: List[CompanyNode] = Field(default_factory=list)
    shareholders: List[ShareholderNode] = Field(default_factory=list)
    relationships: List[EquityRelationship] = Field(default_factory=list)
    additional_data: Dict[str, Any] = Field(default_factory=dict, description="额外数据")


class DiagramResult(BaseModel):
    """图表生成结果"""
    diagram_type: DiagramType
    format: DiagramFormat
    title: Optional[str]
    source_code: Optional[str] = Field(None, description="Mermaid/DOT 源代码")
    rendered_data: Optional[str] = Field(None, description="渲染后的图表数据（base64 或 SVG）")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DiagramLLMGenerateRequest(BaseModel):
    """从文本生成图表请求"""
    text: str = Field(..., description="文本描述")
    diagram_type: DiagramType
    title: Optional[str] = Field(None, description="图表标题")
    format: DiagramFormat = Field(default=DiagramFormat.MERMAID_CODE)
