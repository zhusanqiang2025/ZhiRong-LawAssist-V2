# backend/app/models/risk_analysis.py
"""
风险评估模块数据库模型

包含四个核心表：
1. RiskRulePackage: 风险评估规则包表（新增）
2. RiskAnalysisSession: 风险分析会话主表
3. RiskItem: 具体风险项表
4. RiskAnalysisRule: 风险评估规则表（独立于合同审查规则）
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Boolean, Float
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database import Base


class RiskAnalysisStatus(str, enum.Enum):
    """风险分析状态枚举"""
    PENDING = "pending"           # 等待处理
    PARSING = "parsing"           # 文档解析中
    ANALYZING = "analyzing"       # 分析中
    COMPLETED = "completed"       # 已完成
    FAILED = "failed"             # 失败


class RiskLevel(str, enum.Enum):
    """风险等级枚举"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskRulePackage(Base):
    """
    风险评估规则包表

    用于管理不同场景的规则包，每个规则包包含一组相关的风险评估规则。
    例如：股权穿透分析包、投资项目风险分析包、公司混同风险包等。
    """
    __tablename__ = "risk_rule_packages"

    id = Column(Integer, primary_key=True, index=True)

    # 基本信息
    package_id = Column(String(64), unique=True, index=True, nullable=False, comment="规则包唯一标识")
    package_name = Column(String(128), nullable=False, comment="规则包名称")
    package_category = Column(String(64), index=True, comment="规则包分类：equity_risk/investment_risk/governance_risk")
    description = Column(Text, comment="规则包描述")

    # 适用场景
    applicable_scenarios = Column(JSON, comment="适用场景列表 ['equity_penetration', 'investment_project']")
    target_entities = Column(JSON, comment="目标实体类型 ['company', 'person', 'project']")

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
        return f"<RiskRulePackage {self.package_name} ({self.package_id})>"


class RiskAnalysisSession(Base):
    """风险分析会话主表"""
    __tablename__ = "risk_analysis_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), unique=True, index=True, nullable=False, comment="会话唯一标识")

    # 用户和状态
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, comment="用户ID")
    status = Column(String(32), default=RiskAnalysisStatus.PENDING.value, index=True, comment="分析状态")

    # 分析场景
    scene_type = Column(String(64), nullable=False, comment="分析场景：equity_penetration, contract_risk, compliance_review 等")
    user_description = Column(Text, nullable=True, comment="用户输入的文字描述")
    evaluation_stance = Column(Text, nullable=True, comment="风险评估立场")  # ✅ 新增：风险评估立场

    # 文档关联
    document_ids = Column(JSON, nullable=True, comment="关联的文档路径列表")

    # 文档处理结果（上传阶段保存的UnifiedDocumentService处理结果）
    document_processing_results = Column(JSON, nullable=True, comment="文档处理结果 {filename: {file_path, status, metadata, ...}}")

    # 文档预整理结果（分析阶段DocumentPreorganizationService的处理结果）
    document_preorganization = Column(JSON, nullable=True, comment="文档预整理结果 {classification, quality_scores, summaries, ...}")

    # 分析结果摘要
    summary = Column(Text, nullable=True, comment="总体风险摘要")
    risk_distribution = Column(JSON, nullable=True, comment="风险分布统计 {'high': 3, 'medium': 5, 'low': 2}")
    total_confidence = Column(Float, nullable=True, comment="总体置信度 0-1")

    # WebSocket 连接 ID（用于推送进度）
    websocket_id = Column(String(128), nullable=True, comment="WebSocket连接ID")

    # 报告相关
    report_md = Column(Text, nullable=True, comment="Markdown 格式报告")
    report_json = Column(JSON, nullable=True, comment="结构化 JSON 报告")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
    completed_at = Column(DateTime, nullable=True, comment="完成时间")

    # 历史任务管理字段
    title = Column(String(255), nullable=True, comment="会话标题（用于历史记录显示）")
    is_unread = Column(Boolean, default=True, comment="是否未读")
    is_background = Column(Boolean, default=False, comment="是否为后台任务")

    # 关系
    risk_items = relationship("RiskItem", back_populates="session", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RiskAnalysisSession {self.session_id} - {self.status}>"


class RiskItem(Base):
    """具体风险项表"""
    __tablename__ = "risk_items"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("risk_analysis_sessions.id"), nullable=False, index=True, comment="会话ID")

    # 风险基本信息
    title = Column(String(255), nullable=False, comment="风险点标题")
    description = Column(Text, nullable=False, comment="详细描述")
    risk_level = Column(String(16), nullable=False, comment="风险等级：low/medium/high/critical")
    confidence = Column(Float, default=0.0, comment="置信度 0-1")

    # 详细内容
    reasons = Column(JSON, nullable=True, comment="理由列表 ['reason1', 'reason2']")
    suggestions = Column(JSON, nullable=True, comment="规避建议列表")

    # 来源追踪
    source_type = Column(String(32), nullable=False, comment="来源类型：rule/llm/agent")
    source_rules = Column(JSON, nullable=True, comment="来源规则 ID 列表")

    # 相关文档片段
    related_sections = Column(JSON, nullable=True, comment="相关文档片段列表")

    # 关系图数据（股权穿透场景）
    graph_data = Column(JSON, nullable=True, comment="关系图节点和边数据")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 反向关系
    session = relationship("RiskAnalysisSession", back_populates="risk_items")

    def __repr__(self):
        return f"<RiskItem {self.title} - {self.risk_level}>"


class RiskAnalysisRule(Base):
    """风险评估规则表（独立于合同审查规则）"""
    __tablename__ = "risk_analysis_rules"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True, comment="规则名称")
    description = Column(String(255), nullable=True, comment="规则描述")

    # 规则分类
    scene_type = Column(String(64), nullable=False, comment="适用场景：equity_penetration, contract_risk 等")
    rule_category = Column(String(32), nullable=False, default="custom", comment="规则类型：universal/feature/custom")
    risk_type = Column(String(64), nullable=False, comment="风险类型：payment, liability, compliance 等")

    # 规则内容
    content = Column(Text, nullable=False, comment="规则 Prompt 内容")
    keywords = Column(JSON, nullable=True, comment="关键词列表 ['违约金', '赔偿']")
    pattern = Column(String(512), nullable=True, comment="正则表达式模式")

    # 配置
    is_active = Column(Boolean, default=True, comment="是否启用")
    priority = Column(Integer, default=0, comment="优先级，数字越小越优先")
    default_risk_level = Column(String(16), nullable=True, comment="默认风险等级")

    # 创建者
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    is_system = Column(Boolean, default=False, comment="是否为系统规则")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def __repr__(self):
        return f"<RiskAnalysisRule {self.name} ({self.scene_type})>"
