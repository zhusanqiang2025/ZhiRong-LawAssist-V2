# backend/app/models/litigation_analysis.py
"""
案件分析模块数据库模型

诉讼案件智能分析系统的数据模型，包含：
1. LitigationCasePackage: 案件类型包表
2. LitigationAnalysisSession: 案件分析会话表
3. LitigationCaseItem: 案件分析项表
4. LitigationAnalysisRule: 分析规则表
5. Evidence: 证据记录表
6. TimelineEvent: 时间线事件表
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class LitigationAnalysisStatus(str, enum.Enum):
    """案件分析状态枚举"""
    PENDING = "pending"           # 等待处理
    PARSING = "parsing"           # 文档解析中
    ANALYZING = "analyzing"       # 分析中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


class CaseType(str, enum.Enum):
    """案件类型枚举"""
    CONTRACT_PERFORMANCE = "contract_performance"       # 合同履约分析
    COMPLAINT_DEFENSE = "complaint_defense"             # 起诉状分析
    JUDGMENT_APPEAL = "judgment_appeal"                 # 判决分析
    EVIDENCE_PRESERVATION = "evidence_preservation"     # 保全申请
    ENFORCEMENT = "enforcement"                         # 强制执行
    ARBITRATION = "arbitration"                         # 仲裁程序
    DEBT_COLLECTION = "debt_collection"                # 债务追讨
    LABOR_DISPUTE = "labor_dispute"                     # 劳动争议
    IP_INFRINGEMENT = "ip_infringement"                 # 知识产权
    MARINE_ACCIDENT = "marine_accident"                 # 海事事故


class CasePosition(str, enum.Enum):
    """诉讼地位枚举"""
    PLAINTIFF = "plaintiff"       # 原告
    DEFENDANT = "defendant"       # 被告
    APPELLANT = "appellant"       # 上诉人
    APPELLEE = "appellee"         # 被上诉人
    APPLICANT = "applicant"       # 申请人
    RESPONDENT = "respondent"     # 被申请人


class StrengthLevel(str, enum.Enum):
    """案件强弱等级枚举"""
    STRONG = "strong"             # 强
    MEDIUM = "medium"             # 中等
    WEAK = "weak"                 # 弱


class LitigationCasePackage(Base):
    """
    诉讼案件类型包表

    用于管理不同诉讼场景的分析规则包。
    """
    __tablename__ = "litigation_case_packages"

    id = Column(Integer, primary_key=True, index=True)

    # 基本信息
    package_id = Column(String(64), unique=True, index=True, nullable=False, comment="规则包唯一标识")
    package_name = Column(String(128), nullable=False, comment="规则包名称")
    package_category = Column(String(64), index=True, comment="规则包分类：contract_dispute/labor_dispute等")
    case_type = Column(String(64), index=True, comment="案件类型：contract_performance/complaint_defense等")
    description = Column(Text, comment="规则包描述")

    # 适用场景
    applicable_positions = Column(JSON, comment="适用诉讼地位 ['plaintiff', 'defendant']")
    target_documents = Column(JSON, comment="目标文档类型 ['contract', 'complaint', 'judgment']")

    # 规则列表（JSON 格式存储规则配置）
    rules = Column(JSON, nullable=False, comment="规则列表，每个规则包含 rule_id, rule_name, rule_prompt, priority")

    # 状态管理
    is_active = Column(Boolean, default=True, index=True, comment="是否启用")
    is_system = Column(Boolean, default=False, comment="是否系统预定义")
    version = Column(String(32), comment="版本号")

    # 元数据
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<LitigationCasePackage {self.package_name} ({self.package_id})>"


class LitigationAnalysisSession(Base):
    """
    案件分析会话主表
    """
    __tablename__ = "litigation_analysis_sessions"

    # Pydantic 配置：禁用 model_ 命名空间保护
    class Config:
        protected_namespaces = ()

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False, comment="会话唯一标识")

    # 用户和状态
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    status = Column(String(32), default=LitigationAnalysisStatus.PENDING.value, index=True, comment="分析状态")

    # 案件信息
    case_type = Column(String(64), nullable=False, index=True, comment="案件类型")
    case_position = Column(String(32), comment="诉讼地位")
    user_input = Column(Text, nullable=True, comment="用户输入的案件描述")
    package_id = Column(String(64), index=True, comment="使用的规则包")

    # 文档关联
    document_ids = Column(JSON, nullable=True, comment="关联的文档路径列表")

    # 分析结果摘要
    case_summary = Column(Text, nullable=True, comment="案件概要")
    case_overview = Column(Text, nullable=True, comment="案件全景综述（AI生成的整体概述）")
    win_probability = Column(Float, nullable=True, comment="胜诉概率 0-1")

    # 详细分析结果（JSON 存储）
    case_strength = Column(JSON, nullable=True, comment="案件强弱分析")
    evidence_assessment = Column(JSON, nullable=True, comment="证据评估")
    legal_issues = Column(JSON, nullable=True, comment="争议焦点")
    strategies = Column(JSON, nullable=True, comment="诉讼策略")
    risk_warnings = Column(JSON, nullable=True, comment="风险提示")
    recommendations = Column(JSON, nullable=True, comment="行动建议")

    # 可视化数据
    timeline_events = Column(JSON, nullable=True, comment="时间线事件")
    evidence_chain = Column(JSON, nullable=True, comment="证据链")
    case_diagrams = Column(JSON, nullable=True, comment="案件图表")

    # 多模型分析记录
    model_results = Column(JSON, nullable=True, comment="各模型的分析结果")
    selected_model = Column(String(32), nullable=True, comment="被选中的最优模型")

    # WebSocket 连接 ID（用于推送进度）
    websocket_id = Column(String(128), nullable=True, comment="WebSocket连接ID")

    # 报告相关
    report_md = Column(Text, nullable=True, comment="Markdown 格式报告")
    report_json = Column(JSON, nullable=True, comment="结构化 JSON 报告")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 关系
    case_items = relationship("LitigationCaseItem", back_populates="session", cascade="all, delete-orphan")
    evidence_records = relationship("Evidence", back_populates="session", cascade="all, delete-orphan")
    timeline_events_rel = relationship("TimelineEvent", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<LitigationAnalysisSession {self.session_id} - {self.status}>"


class LitigationCaseItem(Base):
    """
    案件分析项表
    """
    __tablename__ = "litigation_case_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("litigation_analysis_sessions.id"), nullable=False, index=True, comment="会话ID")

    # 分析项基本信息
    item_type = Column(String(32), nullable=False, comment="分析项类型：legal_issue/evidence/strategy/risk")
    title = Column(String(255), nullable=False, comment="标题")
    description = Column(Text, nullable=False, comment="详细描述")

    # 强弱评估
    strength_level = Column(String(16), comment="强弱等级：strong/medium/weak")
    confidence = Column(Float, default=0.0, comment="置信度 0-1")

    # 详细内容
    analysis = Column(JSON, nullable=True, comment="详细分析内容")
    sources = Column(JSON, nullable=True, comment="来源文档")
    legal_basis = Column(JSON, nullable=True, comment="法律依据")

    # 关联
    related_evidence = Column(JSON, nullable=True, comment="相关证据ID列表")
    related_strategies = Column(JSON, nullable=True, comment="相关策略ID列表")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 反向关系
    session = relationship("LitigationAnalysisSession", back_populates="case_items")

    def __repr__(self):
        return f"<LitigationCaseItem {self.title} - {self.item_type}>"


class Evidence(Base):
    """
    证据记录表
    """
    __tablename__ = "litigation_evidence"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("litigation_analysis_sessions.id"), nullable=False, index=True, comment="会话ID")
    evidence_id = Column(String(64), index=True, comment="证据唯一标识")

    # 证据基本信息
    evidence_type = Column(String(32), nullable=False, comment="证据类型：document/witness/expert_opinion等")
    evidence_name = Column(String(255), comment="证据名称")
    description = Column(Text, comment="证据描述")

    # 证明力评估
    admissibility = Column(Boolean, nullable=True, comment="可采性")
    weight = Column(Float, comment="证明力权重 0-1")
    relevance = Column(Float, comment="相关性 0-1")

    # 证明内容
    facts_to_prove = Column(JSON, nullable=True, comment="待证事实列表")
    legal_issues = Column(JSON, nullable=True, comment="相关法律争议")

    # 来源
    source_document_id = Column(String(64), comment="来源文档ID")

    # 状态
    status = Column(String(16), default="pending", comment="状态：pending/admitted/rejected/challenged")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 反向关系
    session = relationship("LitigationAnalysisSession", back_populates="evidence_records")

    def __repr__(self):
        return f"<Evidence {self.evidence_name} - {self.evidence_type}>"


class TimelineEvent(Base):
    """
    时间线事件表
    """
    __tablename__ = "litigation_timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("litigation_analysis_sessions.id"), nullable=False, index=True, comment="会话ID")

    # 事件信息
    event_date = Column(DateTime, nullable=False, index=True, comment="事件日期")
    event_type = Column(String(32), nullable=False, comment="事件类型：contract_signing/breach/filing等")
    description = Column(Text, nullable=False, comment="事件描述")

    # 关联
    related_documents = Column(JSON, nullable=True, comment="相关文档ID列表")
    related_evidence = Column(JSON, nullable=True, comment="相关证据ID列表")

    # 法律意义
    legal_significance = Column(Text, comment="法律意义说明")
    statute_implications = Column(JSON, nullable=True, comment="诉讼时效影响")

    # 重要性
    importance = Column(String(16), default="normal", comment="重要性：critical/important/normal")

    order = Column(Integer, default=0, comment="排序序号")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 反向关系
    session = relationship("LitigationAnalysisSession", back_populates="timeline_events_rel")

    def __repr__(self):
        return f"<TimelineEvent {self.event_type} - {self.event_date}>"
