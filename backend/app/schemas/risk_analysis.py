# backend/app/schemas/risk_analysis.py
"""
风险评估模块的 Pydantic Schema 定义

用于 API 请求和响应的数据验证和序列化
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime


class RiskSectionRef(BaseModel):
    """文档片段引用"""
    doc_id: str = Field(..., description="文档ID")
    page: Optional[int] = Field(None, description="页码")
    text: str = Field(..., description="原文片段")
    highlight: bool = Field(True, description="是否高亮")


class RiskItemCreate(BaseModel):
    """创建风险项请求"""
    title: str = Field(..., description="风险点标题")
    description: str = Field(..., description="详细描述")
    risk_level: str = Field(..., description="风险等级：low/medium/high/critical")
    confidence: float = Field(..., ge=0, le=1, description="置信度 0-1")
    reasons: List[str] = Field(default_factory=list, description="理由列表")
    suggestions: List[str] = Field(default_factory=list, description="规避建议列表")
    source_type: str = Field(..., description="来源类型：rule/llm/agent")
    source_rules: Optional[List[int]] = Field(None, description="来源规则 ID 列表")
    related_sections: Optional[List[RiskSectionRef]] = Field(None, description="相关文档片段")
    graph_data: Optional[Dict[str, Any]] = Field(None, description="关系图数据")


class RiskItemResponse(RiskItemCreate):
    """风险项响应"""
    id: int
    session_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class RiskAnalysisSubmitRequest(BaseModel):
    """提交风险分析请求"""
    scene_type: str = Field(
        ...,
        description="分析场景：equity_penetration, contract_risk, compliance_review, tax_risk"
    )
    user_description: Optional[str] = Field(None, description="用户描述")
    document_ids: Optional[List[str]] = Field(None, description="已上传文档 ID 列表")
    enable_custom_rules: bool = Field(False, description="是否启用用户自定义规则")


class RiskAnalysisSessionResponse(BaseModel):
    """风险分析会话响应"""
    id: int
    session_id: str
    status: str
    scene_type: str
    user_description: Optional[str]
    summary: Optional[str]
    risk_distribution: Optional[Dict[str, int]]
    total_confidence: Optional[float]
    report_md: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True


class RiskAnalysisDetailResponse(RiskAnalysisSessionResponse):
    """风险分析详情响应（包含风险项）"""
    risk_items: List[RiskItemResponse]
    disclaimer: str = "本评估仅供参考，不能替代专业律师意见。"


class RiskAnalysisStatusResponse(BaseModel):
    """风险分析状态响应"""
    session_id: str
    status: str
    summary: Optional[str]
    risk_distribution: Optional[Dict[str, int]]


class RiskAnalysisUploadResponse(BaseModel):
    """文档上传响应"""
    file_id: str
    file_path: str
    message: str


class RiskAnalysisStartResponse(BaseModel):
    """开始分析响应"""
    message: str
    session_id: str


# 规则管理相关 Schema
class RiskAnalysisRuleCreate(BaseModel):
    """创建风险评估规则请求"""
    name: str = Field(..., description="规则名称")
    description: Optional[str] = Field(None, description="规则描述")
    scene_type: str = Field(..., description="适用场景")
    rule_category: str = Field("custom", description="规则类型：universal/feature/custom")
    risk_type: str = Field(..., description="风险类型")
    content: str = Field(..., description="规则 Prompt 内容")
    keywords: Optional[List[str]] = Field(None, description="关键词列表")
    pattern: Optional[str] = Field(None, description="正则表达式模式")
    default_risk_level: Optional[str] = Field(None, description="默认风险等级")


class RiskAnalysisRuleResponse(BaseModel):
    """风险评估规则响应"""
    id: int
    name: str
    description: Optional[str]
    scene_type: str
    rule_category: str
    risk_type: str
    content: str
    keywords: Optional[List[str]]
    pattern: Optional[str]
    is_active: bool
    priority: int
    default_risk_level: Optional[str]
    creator_id: Optional[int]
    is_system: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
