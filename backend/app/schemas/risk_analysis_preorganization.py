# backend/app/schemas/risk_analysis_preorganization.py
"""
文档预整理节点的 Pydantic Schema 定义

用于专业助理节点的数据验证和序列化
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum


class DocumentCategory(str, Enum):
    """文档类型分类"""
    CONTRACT = "contract"                    # 合同协议
    FINANCIAL_REPORT = "financial_report"    # 财务报表
    BUSINESS_LICENSE = "business_license"    # 营业执照/工商信息
    ID_DOCUMENT = "id_document"              # 身份证件
    COURT_DOCUMENT = "court_document"        # 法院文书
    TAX_DOCUMENT = "tax_document"            # 税务文件
    SHAREHOLDER = "shareholder"              # 股权文件
    OTHER = "other"


class DocumentQuality(BaseModel):
    """文档质量评估"""
    overall_score: float = Field(..., ge=0, le=1, description="总体质量分数 0-1")
    completeness: float = Field(..., ge=0, le=1, description="完整度")
    clarity: float = Field(..., ge=0, le=1, description="清晰度（针对扫描件）")
    missing_fields: List[str] = Field(default_factory=list, description="缺失关键字段")
    issues: List[str] = Field(default_factory=list, description="质量问题列表")


class DocumentRelationship(BaseModel):
    """文档间关系"""
    source_doc: str = Field(..., description="源文档路径")
    target_doc: str = Field(..., description="目标文档路径")
    relationship_type: str = Field(..., description="关系类型：supplement/amendment/related/equivalent")
    confidence: float = Field(..., ge=0, le=1, description="关系置信度")
    reason: str = Field(..., description="关系判断理由")


class DocumentSummary(BaseModel):
    """文档智能摘要"""
    file_path: str = Field(..., description="文档路径")
    document_title: Optional[str] = Field(None, description="文档内容标题（如'设备采购合同'）")
    document_type_label: Optional[str] = Field(None, description="文档类型中文标签（如'合同'）")
    document_subtype: Optional[str] = Field(None, description="文档子类型（如'股权转让协议'、'股东会决议'等）")
    document_purpose: Optional[str] = Field(None, description="文档目的（为什么创建这个文档）")
    party_positions: Optional[str] = Field(None, description="各方诉求/立场")
    summary: str = Field(..., description="智能摘要（2-3句话）")
    key_parties: List[str] = Field(default_factory=list, description="关键当事人")
    key_dates: List[str] = Field(default_factory=list, description="关键日期")
    key_amounts: List[str] = Field(default_factory=list, description="关键金额")
    risk_signals: List[str] = Field(default_factory=list, description="风险信号")


class PreorganizedDocuments(BaseModel):
    """预整理后的文档集合"""
    # 原始文档
    raw_documents: List[Dict[str, Any]] = Field(default_factory=list, description="原始文档列表")

    # 分类信息
    document_classification: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="按类型分组的文档路径"
    )

    # 质量评估
    quality_scores: Dict[str, DocumentQuality] = Field(
        default_factory=dict,
        description="每个文档的质量评估"
    )

    # 智能摘要
    document_summaries: Dict[str, DocumentSummary] = Field(
        default_factory=dict,
        description="每个文档的智能摘要"
    )

    # 关系图
    document_relationships: List[DocumentRelationship] = Field(
        default_factory=list,
        description="文档间关系"
    )

    # 重复文档
    duplicates: List[List[str]] = Field(
        default_factory=list,
        description="重复或高度相似的文档对"
    )

    # 重要性排序
    ranked_documents: List[str] = Field(
        default_factory=list,
        description="按重要性排序的文档路径（最重要的在前）"
    )

    # 跨文档关键信息提取
    cross_doc_info: Dict[str, Any] = Field(
        default_factory=dict,
        description="跨文档提取的关键信息"
    )


class DocumentPreorganizationRequest(BaseModel):
    """文档预整理请求"""
    document_paths: List[str] = Field(..., description="文档路径列表")
    user_context: Optional[str] = Field(None, description="用户提供的上下文信息")


class DocumentPreorganizationResponse(BaseModel):
    """文档预整理响应"""
    preorganized_docs: PreorganizedDocuments
    status: str = Field(default="success")
    message: Optional[str] = Field(None, description="处理消息或警告")
