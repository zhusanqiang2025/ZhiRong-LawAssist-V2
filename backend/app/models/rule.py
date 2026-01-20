# backend/app/models/rule.py
"""
审查规则模型

用于管理合同审查的规则配置
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database import Base


class ReviewRule(Base):
    """
    企业审查红线规则表

    功能:
    - 存储合同审查的规则配置
    - 支持规则分类和自定义规则
    - 支持规则优先级和启用/禁用
    """
    __tablename__ = "contract_review_rules"

    # ========== 基本信息 ==========
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), nullable=False, index=True, comment="规则名称，如：预付款红线")
    description = Column(String(255), nullable=True, comment="规则描述")
    content = Column(Text, nullable=False, comment="具体规则 Prompt 内容")
    is_active = Column(Boolean, default=True, comment="是否启用")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")

    # 新增字段：支持规则分类和自定义规则
    rule_category = Column(String(20), nullable=False, default="custom", comment="规则类型：universal/feature/stance/custom")
    creator_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="创建者ID")
    priority = Column(Integer, default=0, comment="优先级，数字越小越优先")
    is_system = Column(Boolean, default=False, comment="是否为系统规则")

    def __repr__(self):
        return f"<ReviewRule {self.name}>"

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "content": self.content,
            "is_active": self.is_active,
            "rule_category": self.rule_category,
            "creator_id": self.creator_id,
            "priority": self.priority,
            "is_system": self.is_system,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
