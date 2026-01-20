# backend/app/models/knowledge_base.py
"""
知识库相关数据库模型
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class KnowledgeBaseConfig(Base):
    """知识库配置表"""
    __tablename__ = "knowledge_base_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL 表示全局配置
    config_key = Column(String(100), unique=True, nullable=False, index=True)  # 配置键
    config_value = Column(JSON, nullable=False)  # 配置值（JSON格式）
    is_active = Column(Boolean, default=True)  # 是否启用
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="knowledge_base_configs")


class UserModulePreference(Base):
    """用户模块偏好设置

    存储用户对每个模块的知识库使用偏好
    """
    __tablename__ = "user_module_preferences"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    module_name = Column(String(50), nullable=False)  # 模块名称：consultation, contract_review, risk_analysis
    knowledge_base_enabled = Column(Boolean, default=False)  # 是否启用知识库
    enabled_stores = Column(JSON)  # 该模块启用的知识库列表
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="module_preferences")

    # 唯一约束
    __table_args__ = (
        # UniqueConstraint('user_id', 'module_name', name='unique_user_module'),
    )


class SystemModuleKnowledgeConfig(Base):
    """系统模块知识库权限配置

    管理员配置每个模块是否可以使用系统级知识库
    """
    __tablename__ = "system_module_kb_configs"

    id = Column(Integer, primary_key=True, index=True)
    module_name = Column(String(50), unique=True, nullable=False, index=True)  # 模块名称
    system_kb_enabled = Column(Boolean, default=False)  # 是否启用系统级知识库
    enabled_system_stores = Column(JSON)  # 启用的系统级知识源列表（如：["本地法律知识库", "飞书知识库"]）
    allow_user_kb = Column(Boolean, default=True)  # 是否允许用户使用私有知识库
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey("users.id"))  # 最后更新者（管理员）

    # 关系
    admin = relationship("User", foreign_keys=[updated_by])


class KnowledgeDocument(Base):
    """知识库文档表

    支持两种类型：
    1. 系统级知识库：user_id=NULL，管理员管理，全局共享
    2. 用户私有知识库：user_id=用户ID，用户自己管理，仅自己可见
    """
    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    doc_id = Column(String(100), unique=True, nullable=False, index=True)  # 文档唯一标识
    title = Column(String(500), nullable=False)  # 文档标题
    content = Column(Text, nullable=False)  # 清洗后的文本内容

    # 知识库类型和可见性
    kb_type = Column(String(20), nullable=False, default="user", index=True)  # 知识库类型：system（系统级）, user（用户私有）
    is_public = Column(Boolean, default=False, index=True)  # 是否公开（仅对用户私有知识库有效）
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # NULL=系统级，非NULL=用户私有

    # 来源信息
    source_type = Column(String(50), nullable=False)  # 来源类型：local, feishu, upload, manual
    source_id = Column(String(200))  # 原始文档 ID（如飞书文档 ID）
    source_url = Column(String(1000))  # 原始 URL

    # 分类信息
    category = Column(String(100))  # 法律分类
    tags = Column(JSON)  # 标签列表

    # 扩展信息（不使用 metadata 因为是 SQLAlchemy 保留字）
    extra_data = Column(JSON)  # 扩展元数据（法律引用、作者等）

    # 向量化信息
    vectorized = Column(Boolean, default=False)  # 是否已向量化
    vector_ids = Column(JSON)  # 向量 ID 列表

    # 状态管理
    status = Column(String(20), default="active", index=True)  # 状态：active（活跃）, archived（归档）, deleted（删除）

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    synced_at = Column(DateTime)  # 最后同步时间（用于外部知识库）

    # 关系
    user = relationship("User", back_populates="knowledge_documents")
