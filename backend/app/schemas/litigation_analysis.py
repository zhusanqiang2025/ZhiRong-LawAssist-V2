# backend/app/schemas/litigation_analysis.py
"""
案件分析模块 Pydantic Schemas (终极补全版)

修复记录：
1. 补全 WebSocketProgressMessage 等消息模型
2. 补全 LitigationAnalysisResult 及其子模型
3. 统一 PartyRole 和 DocumentType 定义
"""

from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum


# ==================== 1. 基础枚举定义 ====================

class CaseTypeEnum(str, Enum):
    CONTRACT_PERFORMANCE = "contract_performance"
    COMPLAINT_DEFENSE = "complaint_defense"
    JUDGMENT_APPEAL = "judgment_appeal"
    EVIDENCE_PRESERVATION = "evidence_preservation"
    ENFORCEMENT = "enforcement"
    ARBITRATION = "arbitration"
    DEBT_COLLECTION = "debt_collection"
    LABOR_DISPUTE = "labor_dispute"
    IP_INFRINGEMENT = "ip_infringement"
    MARINE_ACCIDENT = "marine_accident"
    GENERAL = "general"

class CasePositionEnum(str, Enum):
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"
    APPELLANT = "appellant"
    APPELLEE = "appellee"
    APPLICANT = "applicant"
    RESPONDENT = "respondent"
    THIRD_PARTY = "third_party"
    COURT = "court"
    ARBITRATOR = "arbitrator"
    OTHER_PARTY = "other_party"
    UNKNOWN = "unknown"

class AnalysisScenarioEnum(str, Enum):
    PRE_LITIGATION = "pre_litigation"
    DEFENSE = "defense"
    APPEAL = "appeal"
    EXECUTION = "execution"
    PRESERVATION = "preservation"
    EVIDENCE_COLLECTION = "evidence_collection"
    MEDIATION = "mediation"

class StrengthLevelEnum(str, Enum):
    STRONG = "strong"
    MEDIUM = "medium"
    WEAK = "weak"

class AnalysisStatusEnum(str, Enum):
    PENDING = "pending"
    PARSING = "parsing"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== 2. 规则包模型 ====================

class LitigationCaseRule(BaseModel):
    rule_id: str = Field(..., description="规则ID")
    rule_name: str = Field(..., description="规则名称")
    rule_prompt: str = Field(..., description="规则提示词")
    priority: int = Field(default=0, description="优先级")

class LitigationCasePackageCreate(BaseModel):
    package_name: str
    package_category: str
    case_type: str
    description: Optional[str] = None
    applicable_positions: Optional[List[str]] = None
    target_documents: Optional[List[str]] = None
    rules: List[LitigationCaseRule]
    is_active: Optional[bool] = True

class LitigationCasePackageUpdate(BaseModel):
    package_name: Optional[str] = None
    package_category: Optional[str] = None
    case_type: Optional[str] = None
    description: Optional[str] = None
    applicable_positions: Optional[List[str]] = None
    target_documents: Optional[List[str]] = None
    rules: Optional[List[LitigationCaseRule]] = None
    is_active: Optional[bool] = None

class LitigationCasePackageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    package_id: str
    package_name: str
    package_category: str
    case_type: str
    description: Optional[str]
    applicable_positions: Optional[List[str]]
    target_documents: Optional[List[str]]
    rules: List[LitigationCaseRule]
    is_active: bool
    is_system: bool
    version: Optional[str]
    creator_id: Optional[int]
    created_at: datetime
    updated_at: datetime


# ==================== 3. 预整理业务模型 ====================

class PartyInfo(BaseModel):
    name: str = Field(..., description="主体名称")
    role: str = Field(default="other_party", description="角色")
    identification: Optional[str] = Field(None, description="身份标识")
    description: Optional[str] = Field(None, description="描述")
    confidence: float = Field(default=1.0)
    class Config:
        extra = "ignore"

class LitigationDocumentAnalysis(BaseModel):
    file_id: str
    file_name: str
    file_type: str 
    content_summary: str = ""
    document_title: Optional[str] = None
    document_subtype: Optional[str] = None
    document_purpose: Optional[str] = None
    key_facts: List[str] = Field(default_factory=list)
    key_dates: List[str] = Field(default_factory=list)
    key_amounts: List[str] = Field(default_factory=list)
    parties: List[PartyInfo] = Field(default_factory=list)
    party_positions: Optional[str] = None
    risk_signals: List[str] = Field(default_factory=list)
    litigation_claims: List[str] = Field(default_factory=list)
    case_facts_summary: Optional[str] = None
    judgment_result: Optional[str] = None
    judgment_reasons: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    class Config:
        extra = "ignore"

class DocumentRelationship(BaseModel):
    source_file_id: str = Field(default="", description="源文档ID")
    target_file_id: str = Field(default="", description="目标文档ID")
    doc1_name: Optional[str] = None
    doc2_name: Optional[str] = None
    relationship_type: str
    description: Optional[str] = None
    reasoning: Optional[str] = None
    confidence: float = Field(default=1.0)

class QualityAssessment(BaseModel):
    clarity_score: float = Field(default=0.5)
    completeness_score: float = Field(default=0.5)
    evidence_chain_score: float = Field(default=0.5)

class CrossDocumentInfo(BaseModel):
    all_parties: List[PartyInfo] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    dispute_points: List[Any] = Field(default_factory=list)
    disputed_amount: Optional[str] = None
    case_overview: Optional[str] = None 

class LitigationPreorganizationResult(BaseModel):
    session_id: str
    document_analyses: List[LitigationDocumentAnalysis] = Field(default_factory=list)
    classification: Dict[str, List[str]] = Field(default_factory=dict)
    cross_document_info: Optional[CrossDocumentInfo] = None
    basic_summaries: Optional[Dict[str, LitigationDocumentAnalysis]] = None 
    deep_analysis: Optional[Dict[str, Any]] = None
    integrated_view: Optional[Dict[str, Any]] = None
    document_relationships: List[Any] = Field(default_factory=list)
    quality_assessment: Optional[Any] = None
    processed_at: datetime = Field(default_factory=datetime.now)
    summary: str = ""
    class Config:
        extra = "ignore"


# ==================== 4. 深度分析结果模型 ====================

class EvidenceItem(BaseModel):
    evidence_id: str
    evidence_type: str = "unknown"
    evidence_name: str
    description: str
    admissibility: bool
    weight: float = 0.0
    relevance: float = 0.0
    facts_to_prove: List[str] = Field(default_factory=list)
    status: str

class EvidenceAnalysisResult(BaseModel):
    evidence_items: List[EvidenceItem] = Field(default_factory=list)
    admissible_count: int = 0
    average_weight: float = 0.0
    evidence_gaps: List[str] = Field(default_factory=list)

class Strategy(BaseModel):
    strategy_id: str
    title: str
    description: str
    priority: str = "medium"
    type: str = "general"
    actions: List[str] = Field(default_factory=list)
    expected_outcome: Optional[str] = None
    risks: Optional[List[str]] = None

class CaseStrengthResult(BaseModel):
    overall_strength: float = Field(..., description="总体强度 0-1")
    strength_level: StrengthLevelEnum
    key_facts: List[str] = Field(default_factory=list)
    legal_basis: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)

class TimelineEventData(BaseModel):
    event_date: datetime
    event_type: str
    description: str
    importance: str
    legal_significance: Optional[str]
    related_documents: Optional[List[str]]

class TimelineResult(BaseModel):
    events: List[TimelineEventData] = Field(default_factory=list)
    critical_events: List[TimelineEventData] = Field(default_factory=list)
    statute_implications: Dict[str, Any] = Field(default_factory=dict)
    visualization_data: Dict[str, Any] = Field(default_factory=dict)

class EvidenceChainData(BaseModel):
    fact: str
    evidence: List[EvidenceItem]
    completeness: float
    weak_points: List[str]

class EvidenceChainResult(BaseModel):
    chains: List[EvidenceChainData] = Field(default_factory=list)
    completeness: float = 0.0
    weak_points: List[str] = Field(default_factory=list)
    visualization_data: Dict[str, Any] = Field(default_factory=dict)

class LegalIssue(BaseModel):
    title: str
    description: str
    importance: str

class LitigationAnalysisResult(BaseModel):
    """最终全案分析结果"""
    case_summary: str
    case_strength: Optional[CaseStrengthResult] = None
    evidence_assessment: Optional[EvidenceAnalysisResult] = None
    legal_issues: List[LegalIssue] = Field(default_factory=list)
    timeline: Optional[TimelineResult] = None
    evidence_chain: Optional[EvidenceChainResult] = None
    strategies: List[Strategy] = Field(default_factory=list)
    risk_warnings: List[str] = Field(default_factory=list)
    recommendations: List[Dict[str, str]] = Field(default_factory=list)


# ==================== 5. WebSocket 消息模型 (新增补全) ====================

class WebSocketProgressMessage(BaseModel):
    """WebSocket 进度消息"""
    session_id: str
    status: str
    progress: float = Field(..., ge=0, le=1, description="进度 0-1")
    message: str
    stage: Optional[str] = None

class WebSocketEvidenceMessage(BaseModel):
    """WebSocket 证据分析消息"""
    session_id: str
    type: str = "evidence_analysis"
    data: EvidenceAnalysisResult

class WebSocketStrategyMessage(BaseModel):
    """WebSocket 策略生成消息"""
    session_id: str
    type: str = "strategy_generated"
    strategies: List[Strategy]


# ==================== 6. API 请求/响应模型 ====================

class LitigationAnalysisRequest(BaseModel):
    package_id: str = Field(..., description="规则包ID")
    case_type: str = Field(..., description="案件类型") 
    case_position: str = Field(..., description="诉讼地位")
    analysis_scenario: str = Field(default="pre_litigation", description="分析场景")
    user_input: Optional[str] = Field(None, description="用户输入的案件描述")
    document_ids: List[str] = Field(default_factory=list, description="文档ID列表")
    analysis_mode: str = Field(default="multi", description="分析模式: single/multi")
    selected_model: Optional[str] = Field(None, description="指定模型")

class LitigationAnalysisSessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, protected_namespaces=())
    id: int
    session_id: str
    user_id: int
    status: str
    case_type: str
    case_position: str
    user_input: Optional[str]
    package_id: str
    document_ids: Optional[List[str]]
    case_summary: Optional[str]
    win_probability: Optional[float]
    model_results: Optional[Dict[str, Any]]
    selected_model: Optional[str]
    created_at: datetime
    completed_at: Optional[datetime]

class LitigationAnalysisSessionsListResponse(BaseModel):
    sessions: List[LitigationAnalysisSessionResponse]
    total: int

class LitigationCasePackagesListResponse(BaseModel):
    packages: List[LitigationCasePackageResponse]


# ==================== 7. 常量定义 ====================

DOCUMENT_TYPE_LABELS = {
    "complaint": "起诉状",
    "defense": "答辩状",
    "judgment": "判决书",
    "ruling": "裁定书",
    "evidence_material": "证据材料",
    "agreement": "合同/协议",
    "lawyer_letter": "律师函",
    "arbitration_application": "仲裁申请书",
    "arbitration_award": "仲裁裁决书",
    "execution_application": "强制执行申请书",
    "execution_order": "执行裁定书",
    "acceptance_notice": "受理通知书",
    "court_summons": "传票",
    "other_litigation_doc": "其他文书"
}

PARTY_ROLE_LABELS = {
    "plaintiff": "原告",
    "defendant": "被告",
    "applicant": "申请人",
    "respondent": "被申请人",
    "appellant": "上诉人",
    "appellee": "被上诉人",
    "third_party": "第三人",
    "court": "法院",
    "arbitrator": "仲裁庭",
    "other_party": "其他"
}