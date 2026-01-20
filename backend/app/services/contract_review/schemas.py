from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# --- Stage 1: 合同法律画像 ---
class ContractProfile(BaseModel):
    contract_type: str = Field(..., description="合同的具体法律类型，如'劳动合同','技术服务合同'")
    is_continuous_service: bool = Field(..., description="是否涉及持续性服务")
    is_composite_contract: bool = Field(..., description="是否为混合合同（包含多种法律关系）")
    high_control_indicated: bool = Field(..., description="甲方是否对乙方有强管理/强控制特征")

    # 知识图谱增强字段
    knowledge_graph_match: bool = Field(default=False, description="是否来自知识图谱匹配")
    match_source: Optional[str] = Field(default=None, description="匹配来源: metadata/title/llm_assisted")
    legal_features: Optional[Dict[str, Any]] = Field(default=None, description="完整的7维法律特征（来自知识图谱）")
    llm_suggestion: Optional[str] = Field(default=None, description="LLM 的原始建议（如有）")

# --- Stage 2: 法律关系判断 ---
class LegalRelationshipAnalysis(BaseModel):
    labor_relation_risk: Literal["high", "medium", "low"] = Field(..., description="被认定为事实劳动关系的风险等级")
    tort_risk: Literal["high", "medium", "low"] = Field(..., description="侵权责任风险等级")
    applicable_laws: List[str] = Field(..., description="适用的核心法律法规名称列表")
    conditionally_applicable_laws: List[str] = Field(default=[], description="特定条件下可能适用的法律")

# --- Stage 3: 最终审查结果 (保持原结构) ---
class ReviewIssue(BaseModel):
    issue_type: str = Field(description="问题类型")
    quote: str = Field(description="原文引用")
    explanation: str = Field(description="风险解释")
    suggestion: str = Field(description="修改建议")
    severity: str = Field(description="风险等级: Critical, High, Medium, Low")
    action_type: str = Field(description="操作类型: Revision, Alert")

class ReviewOutput(BaseModel):
    summary: str = Field(description="整体评价")
    issues: List[ReviewIssue] = Field(description="问题列表")