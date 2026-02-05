# backend/app/schemas.py (v3.2 - 完整合并修正版)
from pydantic import BaseModel, EmailStr, field_validator, Field
from typing import Optional, List, Any, Literal, Union, Dict
from datetime import datetime
import re

# =======================
# Token Schemas
# =======================
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenPayload(BaseModel):
    sub: Optional[str] = None

# =======================
# User Schemas
# =======================
class UserBase(BaseModel):
    email: EmailStr
    phone: Optional[str] = None

class UserCreate(UserBase):
    password: str

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is None or v == '':
            return None
        # 简单验证：支持国际号码（可选 + 前缀，10-15位数字）
        cleaned = v.replace('-', '').replace(' ', '')
        if not re.match(r'^\+?\d{10,15}$', cleaned):
            raise ValueError('手机号格式不正确')
        return v

class UserUpdate(UserBase):
    password: Optional[str] = None

class User(UserBase):
    id: int
    phone: Optional[str] = None
    is_admin: bool = False

    class Config:
        from_attributes = True

# =======================
# Task Schemas
# =======================
class TaskBase(BaseModel):
    id: Optional[str] = None
    doc_type: Optional[str] = None
    status: Optional[str] = "pending"
    user_demand: Optional[str] = None

class TaskCreate(TaskBase):
    owner_id: int

class TaskUpdate(BaseModel):
    status: Optional[str] = None
    analysis_report: Optional[str] = None
    final_document: Optional[str] = None
    result: Optional[str] = None
    user_demand: Optional[str] = None

class Task(TaskBase):
    owner_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    analysis_report: Optional[str] = None
    final_document: Optional[str] = None
    result: Optional[str] = None

    class Config:
        from_attributes = True

# =======================
# Contract Template Schemas
# =======================

# 基础字段
class ContractTemplateBase(BaseModel):
    name: str
    category: str
    subcategory: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = False 
    keywords: Optional[List[str]] = []
    price: Optional[float] = 0.0

# 创建时的请求模型
class ContractTemplateCreate(ContractTemplateBase):
    pass

# 更新时的请求模型
class ContractTemplateUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None

# 响应给前端的模型
class ContractTemplateResponse(ContractTemplateBase):
    id: str
    file_url: str
    file_name: str
    file_size: int
    file_type: str
    
    owner_id: Optional[int] = None
    download_count: int
    rating: float
    status: str
    is_featured: bool
    
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True

# 搜索请求体
class ContractTemplateSearchRequest(BaseModel):
    query: str
    category: Optional[str] = None
    max_results: int = 20
    include_recommendations: bool = True

# 搜索响应体
class ContractTemplateSearchResponse(BaseModel):
    query: str
    templates: List[ContractTemplateResponse]
    recommendations: List[Any] = []
    total_count: int
    search_intent: Optional[str] = None
    processing_time: float

# =======================
# Category Schemas (v2.0 - 支持层级)
# =======================
class CategoryBase(BaseModel):
    name: str
    sort_order: Optional[int] = 0
    is_active: Optional[bool] = True
    parent_id: Optional[int] = None

class CategoryCreate(CategoryBase):
    pass

class CategoryUpdate(CategoryBase):
    pass

class CategoryResponse(CategoryBase):
    id: int
    # 简单的嵌套返回，用于前端构建树
    children: List['CategoryResponse'] = [] 
    
    class Config:
        from_attributes = True

# =======================
# Contract Review Schemas (v3.2 - Hub-and-Spoke 核心增强)
# =======================

# 1. 规则基础模型 (Unified)
class ReviewRuleBase(BaseModel):
    name: str
    description: Optional[str] = None
    content: str
    rule_category: str  # universal/feature/stance/custom
    priority: int = 0
    is_active: bool = True
    
    # ✅ [核心新增] Hub-and-Spoke 关联字段
    # 前端传参示例: [101, 102]
    apply_to_category_ids: Optional[List[int]] = [] 
    
    # 前端传参示例: "buyer"
    target_stance: Optional[str] = None 

# 2. 规则创建模型
class RuleCreate(ReviewRuleBase):
    # is_system 通常由后端权限判断，这里作为可选参数
    is_system: bool = False

# 3. 规则更新模型
class RuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    content: Optional[str] = None
    rule_category: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    
    # ✅ 允许更新关联
    apply_to_category_ids: Optional[List[int]] = None
    target_stance: Optional[str] = None

# 4. 规则响应模型 (用于列表展示)
class ReviewRuleOut(ReviewRuleBase):
    id: int
    is_system: bool
    creator_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    # 确保列表不为 None
    apply_to_category_ids: List[int] = []

    class Config:
        from_attributes = True

# 5. 为了兼容 Admin API 旧接口定义的别名 (如有必要)
class ReviewRuleCreate(RuleCreate):
    pass

class ReviewRuleUpdate(RuleUpdate):
    pass

# =======================
# Review Item & Contract Schemas
# =======================

class ReviewItemBase(BaseModel):
    issue_type: str
    quote: str
    explanation: str
    suggestion: str
    severity: str
    action_type: str = "Revision" # Revision 或 Alert

class ReviewItemUpdate(BaseModel):
    """用于前端更新人工决策状态"""
    item_status: Optional[str] = None # Approved / Rejected / Solved
    final_text: Optional[str] = None
    human_comment: Optional[str] = None

class ReviewItemOut(ReviewItemBase):
    id: int
    contract_id: int
    item_status: str
    final_text: Optional[str]
    human_comment: Optional[str]
    
    class Config:
        from_attributes = True

# 合同元数据模型
class ContractMetadataSchema(BaseModel):
    contract_name: Optional[str] = None
    parties: Optional[str] = None
    amount: Optional[str] = None
    contract_type: Optional[str] = None
    core_terms: Optional[Union[str, List[str]]] = None

    @field_validator('core_terms', mode='before')
    @classmethod
    def validate_core_terms(cls, v):
        if v is None: return None
        if isinstance(v, list): return ', '.join(str(item) for item in v)
        return str(v)

    @field_validator('parties', mode='before')
    @classmethod
    def validate_parties(cls, v):
        if v is None: return None
        if isinstance(v, list): return '; '.join(str(item) for item in v)
        return str(v)

# 合同主表模型
class ContractDocBase(BaseModel):
    title: str

class ContractDocCreate(ContractDocBase):
    pass

class ContractDocUpdate(BaseModel):
    status: Optional[str] = None
    metadata_info: Optional[ContractMetadataSchema] = None
    stance: Optional[str] = None

class ContractDocOut(ContractDocBase):
    id: int
    status: str
    original_file_path: Optional[str]
    pdf_converted_path: Optional[str]
    final_docx_path: Optional[str]
    
    metadata_info: Optional[ContractMetadataSchema] = None
    stance: Optional[str] = None
    
    # 嵌套关联的审查项
    review_items: List[ReviewItemOut] = []
    
    # 关联分类 (简单返回)
    category_id: Optional[int] = None
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

# =======================
# Contract Review Output Schema (AI 结构化输出)
# =======================

class ReviewIssue(BaseModel):
    """单个审查问题"""
    issue_type: str
    quote: str
    explanation: str
    suggestion: str
    legal_basis: str = ""
    severity: Literal["Low", "Medium", "High", "Critical"]
    action_type: Literal["Revision", "Alert"]

class ReviewOutput(BaseModel):
    """AI 深度审查的完整结构化输出"""
    issues: List[ReviewIssue]

# =======================
# JSON 规则迁移辅助 Schemas
# (仅用于 JSON 文件解析，不用于 API 创建)
# =======================

class RuleInstruction(BaseModel):
    focus: str
    instruction: str

class FeatureRuleCategory(BaseModel):
    description: str
    rules: List[RuleInstruction]

class StanceRuleRole(BaseModel):
    role_definition: str
    rules: List[RuleInstruction]

class ReviewRulesConfig(BaseModel):
    version: str
    description: str
    universal_rules: FeatureRuleCategory
    feature_rules: dict
    stance_rules: dict

class UniversalRule(BaseModel):
    id: str
    category: str
    instruction: str

class UniversalRulesOut(BaseModel):
    name: str
    description: str
    rules: List[UniversalRule]

class FeatureRuleOut(BaseModel):
    feature_type: str
    feature_value: str
    rules: List[RuleInstruction]

class StanceRuleOut(BaseModel):
    party: str
    role_definition: str
    rules: List[RuleInstruction]
    
# =======================
# Risk Analysis Schemas (必须保留)
# =======================
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

# 规则管理相关 Schema (风险评估专用)
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